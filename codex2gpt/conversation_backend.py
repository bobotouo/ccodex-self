"""ChatGPT conversation API client for image generation.

Ported from chatgpt2api's OpenAIBackendAPI, adapted for codex2gpt's
account pool and HTTP request patterns.
"""

import base64
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional

from codex2gpt.pow import build_legacy_requirements_token, build_proof_token, parse_pow_resources
from codex2gpt.turnstile import solve_turnstile_token

IMAGE_MODELS = {"gpt-image-2", "codex-gpt-image-2"}

DEFAULT_POW_SCRIPT = "https://chatgpt.com/backend-api/sentinel/sdk.js"
CODEX_IMAGE_MODEL = "codex-gpt-image-2"

_browser_user_agent = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
)
_browser_sec_ch_ua = '"Microsoft Edge";v="143", "Chromium";v="143", "Not A(Brand";v="24"'


@dataclass
class ChatRequirements:
    token: str
    proof_token: str = ""
    turnstile_token: str = ""
    so_token: str = ""


@dataclass
class ImageResult:
    url: str
    revised_prompt: str = ""
    file_id: str = ""


def _new_uuid() -> str:
    return str(uuid.uuid4())


def _ensure_ok(status_code: int, context: str, body: str = ""):
    if 200 <= status_code < 300:
        return
    raise RuntimeError(f"{context} failed: status={status_code}, body={body[:500]}")


def _image_model_slug(model: str) -> str:
    model = str(model or "").strip()
    if model == "gpt-image-2":
        return "gpt-5-3"
    if model == CODEX_IMAGE_MODEL:
        return model
    return "auto"


def _build_image_prompt(prompt: str, size: str | None) -> str:
    if not size:
        return prompt
    if size not in {"1:1", "16:9", "9:16", "4:3", "3:4"}:
        return f"{prompt.strip()}\n\nOutput the image with aspect ratio {size}."
    hint = {
        "1:1": "Output as 1:1 square composition, subject centered.",
        "16:9": "Output as 16:9 landscape composition, suitable for wide displays.",
        "9:16": "Output as 9:16 portrait composition, suitable for vertical displays.",
        "4:3": "Output as 4:3 ratio, balancing width and height.",
        "3:4": "Output as 3:4 ratio, vertical composition for portraits.",
    }[size]
    return f"{prompt.strip()}\n\n{hint}"


def _iter_sse_lines(response) -> Iterator[str]:
    """Parse SSE data lines from an HTTP response."""
    buffer = b""
    while True:
        chunk = response.read(4096)
        if not chunk:
            break
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            decoded = line.decode("utf-8", errors="replace").strip()
            if decoded.startswith("data:"):
                payload = decoded[5:].strip()
                if payload:
                    yield payload


class ConversationBackendClient:
    """ChatGPT web backend client for image generation.

    Uses /backend-api/conversation (not /backend-api/codex/responses).
    Requires browser fingerprinting and PoW challenge solving.
    """

    BASE_URL = "https://chatgpt.com"

    def __init__(self, access_token: str, proxy_url: str | None = None, account_name: str = ""):
        self.access_token = access_token
        self.proxy_url = proxy_url
        self.account_name = account_name
        self.device_id = _new_uuid()
        self.session_id = _new_uuid()
        self.pow_script_sources: list[str] = []
        self.pow_data_build = ""

    def _request_headers(self, path: str, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": _browser_user_agent,
            "Origin": self.BASE_URL,
            "Referer": self.BASE_URL + "/",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-US;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": _browser_sec_ch_ua,
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "OAI-Device-Id": self.device_id,
            "OAI-Session-Id": self.session_id,
            "OAI-Language": "en-US",
            "X-OpenAI-Target-Path": path,
            "X-OpenAI-Target-Route": path,
            "Authorization": f"Bearer {self.access_token}",
        }
        if extra:
            headers.update(extra)
        return headers

    def _bootstrap_headers(self) -> dict[str, str]:
        return {
            "User-Agent": _browser_user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Sec-Ch-Ua": _browser_sec_ch_ua,
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Authorization": f"Bearer {self.access_token}",
        }

    def _do_request(self, url: str, headers: dict[str, str], data: bytes | None = None,
                    method: str = "GET", timeout: int = 60, stream: bool = False):
        """Execute an HTTP request using urllib with optional proxy."""
        req = urllib.request.Request(url, method=method)
        for key, value in headers.items():
            req.add_header(key, value)
        if data is not None:
            req.data = data

        if self.proxy_url:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": self.proxy_url, "https": self.proxy_url})
            )
            return opener.open(req, timeout=timeout)
        return urllib.request.urlopen(req, timeout=timeout)

    def _do_json_request(self, path: str, body: dict | None = None, method: str = "GET",
                         extra_headers: dict[str, str] | None = None, timeout: int = 60) -> dict:
        """Execute a JSON API request and return parsed response."""
        url = self.BASE_URL + path
        headers = self._request_headers(path, extra_headers)
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
        data = json.dumps(body).encode() if body is not None else None
        response = self._do_request(url, headers, data=data, method=method, timeout=timeout)
        status = getattr(response, "status", 200)
        body_bytes = response.read()
        response.close()
        _ensure_ok(status, path, body_bytes.decode("utf-8", errors="replace"))
        if body_bytes.strip():
            return json.loads(body_bytes)
        return {}

    def _bootstrap(self) -> None:
        """Warm up: fetch chatgpt.com to extract PoW script URLs."""
        url = self.BASE_URL + "/"
        req = urllib.request.Request(url)
        for key, value in self._bootstrap_headers().items():
            req.add_header(key, value)
        if self.proxy_url:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": self.proxy_url, "https": self.proxy_url})
            )
            response = opener.open(req, timeout=30)
        else:
            response = urllib.request.urlopen(req, timeout=30)
        status = getattr(response, "status", 200)
        html = response.read().decode("utf-8", errors="replace")
        response.close()
        _ensure_ok(status, "bootstrap")
        self.pow_script_sources, self.pow_data_build = parse_pow_resources(html)
        if not self.pow_script_sources:
            self.pow_script_sources = [DEFAULT_POW_SCRIPT]

    def _get_chat_requirements(self) -> ChatRequirements:
        """Get sentinel tokens (PoW + Turnstile)."""
        path = "/backend-api/sentinel/chat-requirements"
        body = {"p": build_legacy_requirements_token(
            _browser_user_agent, self.pow_script_sources, self.pow_data_build
        )}
        data = self._do_json_request(path, body=body, method="POST")
        raw = data or {}

        if (raw.get("arkose") or {}).get("required"):
            raise RuntimeError("sentinel requires arkose token (not implemented)")

        proof_token = ""
        proof_info = raw.get("proofofwork") or {}
        if proof_info.get("required"):
            proof_token = build_proof_token(
                proof_info.get("seed", ""),
                proof_info.get("difficulty", ""),
                _browser_user_agent,
                script_sources=self.pow_script_sources,
                data_build=self.pow_data_build,
            )

        turnstile_token = ""
        turnstile_info = raw.get("turnstile") or {}
        if turnstile_info.get("required") and turnstile_info.get("dx"):
            turnstile_token = solve_turnstile_token(turnstile_info["dx"], body["p"]) or ""

        token = raw.get("token", "")
        if not token:
            raise RuntimeError("missing sentinel chat requirements token")
        return ChatRequirements(
            token=token,
            proof_token=proof_token,
            turnstile_token=turnstile_token,
            so_token=raw.get("so_token", ""),
        )

    def _conversation_headers(self, path: str, requirements: ChatRequirements,
                              accept: str = "text/event-stream") -> dict[str, str]:
        extra = {
            "Accept": accept,
            "Content-Type": "application/json",
            "OpenAI-Sentinel-Chat-Requirements-Token": requirements.token,
        }
        if requirements.proof_token:
            extra["OpenAI-Sentinel-Proof-Token"] = requirements.proof_token
        if requirements.turnstile_token:
            extra["OpenAI-Sentinel-Turnstile-Token"] = requirements.turnstile_token
        if requirements.so_token:
            extra["OpenAI-Sentinel-SO-Token"] = requirements.so_token
        if accept == "text/event-stream":
            extra["X-Oai-Turn-Trace-Id"] = _new_uuid()
        return self._request_headers(path, extra)

    def _prepare_image_conversation(self, prompt: str, requirements: ChatRequirements,
                                    model: str) -> str:
        """Get conduit token for image generation."""
        path = "/backend-api/f/conversation/prepare"
        payload = {
            "action": "next",
            "fork_from_shared_post": False,
            "parent_message_id": _new_uuid(),
            "model": _image_model_slug(model),
            "client_prepare_state": "success",
            "timezone_offset_min": -480,
            "timezone": "Asia/Shanghai",
            "conversation_mode": {"kind": "primary_assistant"},
            "system_hints": ["picture_v2"],
            "partial_query": {
                "id": _new_uuid(),
                "author": {"role": "user"},
                "content": {"content_type": "text", "parts": [prompt]},
            },
            "supports_buffering": True,
            "supported_encodings": ["v1"],
            "client_contextual_info": {"app_name": "chatgpt.com"},
        }
        headers = self._request_headers(path, {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "OpenAI-Sentinel-Chat-Requirements-Token": requirements.token,
        })
        if requirements.proof_token:
            headers["OpenAI-Sentinel-Proof-Token"] = requirements.proof_token
        url = self.BASE_URL + path
        data_bytes = json.dumps(payload).encode()
        response = self._do_request(url, headers, data=data_bytes, method="POST", timeout=60)
        status = getattr(response, "status", 200)
        body = response.read()
        response.close()
        _ensure_ok(status, path, body.decode("utf-8", errors="replace"))
        return json.loads(body).get("conduit_token", "")

    def _upload_image(self, image_b64: str, file_name: str = "image.png") -> dict[str, Any]:
        """3-step image upload: create -> Azure blob -> confirm."""
        data = base64.b64decode(image_b64.split(",", 1)[1] if image_b64.startswith("data:") else image_b64)

        path = "/backend-api/files"
        meta = self._do_json_request(path, body={
            "file_name": file_name,
            "file_size": len(data),
            "use_case": "multimodal",
            "width": 1024,
            "height": 1024,
        }, method="POST", extra_headers={"Content-Type": "application/json", "Accept": "application/json"})

        time.sleep(0.5)

        upload_url = meta.get("upload_url", "")
        upload_headers = {
            "Content-Type": "image/png",
            "x-ms-blob-type": "BlockBlob",
            "x-ms-version": "2020-04-08",
            "Origin": self.BASE_URL,
            "Referer": self.BASE_URL + "/",
            "User-Agent": _browser_user_agent,
        }
        req = urllib.request.Request(upload_url, data=data, method="PUT")
        for k, v in upload_headers.items():
            req.add_header(k, v)
        if self.proxy_url:
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": self.proxy_url, "https": self.proxy_url})
            )
            upload_resp = opener.open(req, timeout=120)
        else:
            upload_resp = urllib.request.urlopen(req, timeout=120)
        upload_status = getattr(upload_resp, "status", 200)
        upload_resp.read()
        upload_resp.close()
        _ensure_ok(upload_status, "image_upload")

        confirm_path = f"/backend-api/files/{meta['file_id']}/uploaded"
        self._do_json_request(confirm_path, body={}, method="POST",
                              extra_headers={"Content-Type": "application/json", "Accept": "application/json"})

        return {
            "file_id": meta.get("file_id", ""),
            "file_name": file_name,
            "file_size": len(data),
            "mime_type": "image/png",
            "width": 1024,
            "height": 1024,
        }

    def _start_image_generation(self, prompt: str, requirements: ChatRequirements,
                                conduit_token: str, model: str,
                                references: list[dict] | None = None) -> tuple[int, Iterator[str]]:
        """Start image generation SSE stream. Returns (status_code, sse_payloads)."""
        references = references or []
        parts = [{
            "content_type": "image_asset_pointer",
            "asset_pointer": f"file-service://{item['file_id']}",
            "width": item["width"],
            "height": item["height"],
            "size_bytes": item["file_size"],
        } for item in references]
        parts.append(prompt)
        content = {"content_type": "multimodal_text", "parts": parts} if references else {"content_type": "text", "parts": [prompt]}
        metadata = {
            "developer_mode_connector_ids": [],
            "selected_github_repos": [],
            "selected_all_github_repos": False,
            "system_hints": ["picture_v2"],
            "serialization_metadata": {"custom_symbol_offsets": []},
        }
        if references:
            metadata["attachments"] = [{
                "id": item["file_id"],
                "mimeType": item["mime_type"],
                "name": item["file_name"],
                "size": item["file_size"],
                "width": item["width"],
                "height": item["height"],
            } for item in references]
        payload = {
            "action": "next",
            "messages": [{
                "id": _new_uuid(),
                "author": {"role": "user"},
                "create_time": time.time(),
                "content": content,
                "metadata": metadata,
            }],
            "parent_message_id": _new_uuid(),
            "model": _image_model_slug(model),
            "client_prepare_state": "sent",
            "timezone_offset_min": -480,
            "timezone": "Asia/Shanghai",
            "conversation_mode": {"kind": "primary_assistant"},
            "enable_message_followups": True,
            "system_hints": ["picture_v2"],
            "supports_buffering": True,
            "supported_encodings": ["v1"],
            "client_contextual_info": {
                "is_dark_mode": False,
                "time_since_loaded": 1200,
                "page_height": 1072,
                "page_width": 1724,
                "pixel_ratio": 1.2,
                "screen_height": 1440,
                "screen_width": 2560,
                "app_name": "chatgpt.com",
            },
            "paragen_cot_summary_display_override": "allow",
            "force_parallel_switch": "auto",
        }
        path = "/backend-api/f/conversation"
        headers = self._conversation_headers(path, requirements, "text/event-stream")
        url = self.BASE_URL + path
        data_bytes = json.dumps(payload).encode()
        response = self._do_request(url, headers, data=data_bytes, method="POST", timeout=300)
        status = getattr(response, "status", 200)
        _ensure_ok(status, path)
        return status, _iter_sse_lines(response)

    def _get_conversation(self, conversation_id: str) -> dict:
        path = f"/backend-api/conversation/{conversation_id}"
        return self._do_json_request(path, method="GET")

    def _extract_image_tool_records(self, data: dict) -> list[dict]:
        mapping = data.get("mapping") or {}
        file_pat = re.compile(r"file-service://([A-Za-z0-9_-]+)")
        sed_pat = re.compile(r"sediment://([A-Za-z0-9_-]+)")
        records = []
        for message_id, node in mapping.items():
            message = (node or {}).get("message") or {}
            author = message.get("author") or {}
            metadata = message.get("metadata") or {}
            content = message.get("content") or {}
            if author.get("role") != "tool":
                continue
            if metadata.get("async_task_type") != "image_gen":
                continue
            file_ids, sediment_ids = [], []
            for part in content.get("parts") or []:
                text = (part.get("asset_pointer") or "") if isinstance(part, dict) else (part if isinstance(part, str) else "")
                file_ids.extend(f for f in file_pat.findall(text) if f not in file_ids)
                sediment_ids.extend(s for s in sed_pat.findall(text) if s not in sediment_ids)
            records.append({"message_id": message_id, "file_ids": file_ids, "sediment_ids": sediment_ids})
        return records

    def _poll_image_results(self, conversation_id: str, timeout_secs: float = 120.0) -> tuple[list[str], list[str]]:
        start = time.time()
        while time.time() - start < timeout_secs:
            conv = self._get_conversation(conversation_id)
            file_ids, sediment_ids = [], []
            for record in self._extract_image_tool_records(conv):
                file_ids.extend(f for f in record["file_ids"] if f not in file_ids)
                sediment_ids.extend(s for s in record["sediment_ids"] if s not in sediment_ids)
            if file_ids:
                return file_ids, sediment_ids
            if sediment_ids:
                return [], sediment_ids
            time.sleep(4)
        return [], []

    def _get_file_download_url(self, file_id: str) -> str:
        path = f"/backend-api/files/{file_id}/download"
        data = self._do_json_request(path, method="GET")
        return data.get("download_url") or data.get("url") or ""

    def _get_attachment_download_url(self, conversation_id: str, attachment_id: str) -> str:
        path = f"/backend-api/conversation/{conversation_id}/attachment/{attachment_id}/download"
        data = self._do_json_request(path, method="GET")
        return data.get("download_url") or data.get("url") or ""

    def _resolve_image_urls(self, conversation_id: str, file_ids: list[str],
                            sediment_ids: list[str]) -> list[str]:
        urls = []
        for file_id in file_ids:
            if file_id == "file_upload":
                continue
            try:
                url = self._get_file_download_url(file_id)
                if url:
                    urls.append(url)
            except Exception:
                continue
        if urls or not conversation_id:
            return urls
        for sed_id in sediment_ids:
            try:
                url = self._get_attachment_download_url(conversation_id, sed_id)
                if url:
                    urls.append(url)
            except Exception:
                continue
        return urls

    def resolve_conversation_image_urls(self, conversation_id: str, file_ids: list[str],
                                        sediment_ids: list[str], poll: bool = True) -> list[str]:
        file_ids = [f for f in file_ids if f != "file_upload"]
        sediment_ids = list(sediment_ids)
        if poll and conversation_id and not file_ids and not sediment_ids:
            polled_f, polled_s = self._poll_image_results(conversation_id)
            file_ids.extend(f for f in polled_f if f and f not in file_ids)
            sediment_ids.extend(s for s in polled_s if s and s not in sediment_ids)
        return self._resolve_image_urls(conversation_id, file_ids, sediment_ids)

    def download_image_bytes(self, urls: list[str]) -> list[bytes]:
        images = []
        for url in urls:
            response = urllib.request.urlopen(url, timeout=120) if not self.proxy_url else (
                urllib.request.build_opener(
                    urllib.request.ProxyHandler({"http": self.proxy_url, "https": self.proxy_url})
                ).open(url, timeout=120)
            )
            images.append(response.read())
            response.close()
        return images

    def generate_image(self, prompt: str, n: int = 1, size: str | None = None,
                       model: str = "gpt-image-2") -> list[ImageResult]:
        """Generate images via the conversation API.

        Returns a list of ImageResult with base64-encoded image data.
        """
        all_results: list[ImageResult] = []
        enhanced_prompt = _build_image_prompt(prompt, size)

        for index in range(n):
            self._bootstrap()
            requirements = self._get_chat_requirements()
            conduit_token = self._prepare_image_conversation(enhanced_prompt, requirements, model)
            status, sse_payloads = self._start_image_generation(
                enhanced_prompt, requirements, conduit_token, model
            )

            conversation_id = ""
            file_ids: list[str] = []
            sediment_ids: list[str] = []

            for payload in sse_payloads:
                cid_match = re.search(r'"conversation_id"\s*:\s*"([^"]+)"', payload)
                if cid_match and not conversation_id:
                    conversation_id = cid_match.group(1)
                file_ids.extend(f for f in re.findall(r"(file[-_][A-Za-z0-9]+)", payload) if f not in file_ids)
                sediment_ids.extend(s for s in re.findall(r"sediment://([A-Za-z0-9_-]+)", payload) if s not in sediment_ids)

            urls = self.resolve_conversation_image_urls(conversation_id, file_ids, sediment_ids)
            if not urls:
                raise RuntimeError("image generation produced no downloadable images")

            image_bytes_list = self.download_image_bytes(urls)
            for img_bytes in image_bytes_list:
                b64 = base64.b64encode(img_bytes).decode("ascii")
                all_results.append(ImageResult(
                    url="",
                    revised_prompt=prompt,
                    file_id="",
                ))
                all_results[-1].url = b64  # temporarily store b64

        return all_results

    def generate_image_b64(self, prompt: str, n: int = 1, size: str | None = None,
                           model: str = "gpt-image-2") -> dict[str, Any]:
        """Generate images and return OpenAI-compatible response dict."""
        results = self.generate_image(prompt, n=n, size=size, model=model)
        data = []
        for result in results:
            data.append({
                "b64_json": result.url,
                "revised_prompt": result.revised_prompt,
            })
        return {"created": int(time.time()), "data": data}
