"""ChatGPT conversation API client for image generation.

Ported from chatgpt2api's OpenAIBackendAPI, adapted for codex2gpt's
account pool and HTTP request patterns.
"""


class ImageGenerationStartedError(RuntimeError):
    """Raised when image generation was successfully started (tool_invoked=True)
    but we timed out waiting for the result to appear in the conversation.
    Unlike a quota error, retrying with a different account would waste that
    account's daily quota too — the original image may still finish later.
    """


class ImageQuotaExhaustedError(RuntimeError):
    """Raised when ChatGPT explicitly reports the account's image generation
    quota is exhausted (system_error in conversation or known quota message).
    restore_at is the ISO timestamp when the quota will reset (may be empty).
    """
    def __init__(self, message: str, restore_at: str = ""):
        super().__init__(message)
        self.restore_at = restore_at

import base64
import http.client
import io
import json
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from http.cookiejar import CookieJar
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
        # Persist cookies across bootstrap / API / estuary (matches browser Session behavior).
        self._cookie_jar = CookieJar()
        handlers = [urllib.request.HTTPCookieProcessor(self._cookie_jar)]
        if proxy_url:
            handlers.append(
                urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
            )
        self._opener = urllib.request.build_opener(*handlers)

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

        auth_val = headers.get("Authorization", "")
        print(f"[img-debug] HTTP {method} {url} auth={auth_val[:40]}...", flush=True)
        return self._opener.open(req, timeout=timeout)

    def _do_json_request(self, path: str, body: dict | None = None, method: str = "GET",
                         extra_headers: dict[str, str] | None = None, timeout: int = 60) -> dict:
        """Execute a JSON API request and return parsed response."""
        url = self.BASE_URL + path
        headers = self._request_headers(path, extra_headers)
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
        data = json.dumps(body).encode() if body is not None else None
        try:
            response = self._do_request(url, headers, data=data, method=method, timeout=timeout)
        except urllib.error.HTTPError as e:
            resp_body = ""
            try:
                resp_body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            print(f"[img-debug] JSON request HTTPError: {method} {path} status={e.code} body={resp_body}", flush=True)
            raise
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
        try:
            response = self._opener.open(req, timeout=30)
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            print(f"[img-debug] bootstrap HTTPError: status={e.code} url={url} body={body}", flush=True)
            raise
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
                              accept: str = "text/event-stream", conduit_token: str = "") -> dict[str, str]:
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
        if conduit_token:
            extra["X-Conduit-Token"] = conduit_token
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
        headers = self._conversation_headers(path, requirements, "text/event-stream", conduit_token)
        url = self.BASE_URL + path
        data_bytes = json.dumps(payload).encode()
        # Per-chunk read uses this socket timeout; keep moderate vs max_wall_seconds so we
        # re-check the SSE deadline between reads (300s masked a 240s wall clock).
        response = self._do_request(url, headers, data=data_bytes, method="POST", timeout=75)
        status = getattr(response, "status", 200)
        _ensure_ok(status, path)
        return status, response

    def _consume_sse_for_image_metadata(self, response, *, max_wall_seconds: float = 240.0):
        """Read SSE until we have conversation_id + file refs, EOF, or wall-clock deadline.

        Key signals parsed from upstream events (same as chatgpt2api):
        - server_ste_metadata.tool_invoked=false  → ChatGPT did NOT call image tool → reject fast
        - server_ste_metadata.turn_use_case='text' → text-only reply → reject fast
        - moderation.blocked=true                 → content blocked → reject fast
        - file-service:// / sediment://           → image asset ready → success

        Returns (conversation_id, file_ids, sediment_ids, tool_invoked, turn_use_case, blocked).
        """
        conversation_id = ""
        file_ids: list[str] = []
        sediment_ids: list[str] = []
        # SSE metadata signals (chatgpt2api: server_ste_metadata)
        tool_invoked: bool | None = None  # None = unknown, False = no tool called
        turn_use_case: str = ""           # "text" = text-only reply
        blocked: bool = False
        deadline = time.monotonic() + max(30.0, max_wall_seconds)
        buffer = b""
        file_service_pat = re.compile(r"file-service://([A-Za-z0-9_-]+)")
        cid_at: float | None = None
        _debug_post_meta_count = 0   # count payloads after server_ste_metadata for debug
        _debug_saw_meta = False
        try:
            while time.monotonic() < deadline:
                try:
                    chunk = response.read(4096)
                except urllib.error.URLError as exc:
                    if isinstance(getattr(exc, "reason", None), socket.timeout):
                        print(
                            "[img-debug] SSE: read timed out — stopping stream"
                            + (" (will poll)" if conversation_id else ""),
                            flush=True,
                        )
                        break
                    raise
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if not decoded.startswith("data:"):
                        continue
                    payload_str = decoded[5:].strip()
                    if not payload_str or payload_str == "[DONE]":
                        continue

                    # Extract conversation_id via regex (works even before JSON parse)
                    cid_match = re.search(r'"conversation_id"\s*:\s*"([^"]+)"', payload_str)
                    if cid_match and not conversation_id:
                        conversation_id = cid_match.group(1)
                        cid_at = time.monotonic()

                    # Extract file-service:// / sediment:// asset refs (only from image_gen tool)
                    # Only count refs inside image tool messages — check for async_task_type:image_gen
                    is_image_tool = '"async_task_type":"image_gen"' in payload_str or '"async_task_type": "image_gen"' in payload_str
                    if is_image_tool:
                        for fid in file_service_pat.findall(payload_str):
                            if fid not in file_ids and fid != "file_upload":
                                file_ids.append(fid)
                        for s in re.findall(r"sediment://([A-Za-z0-9_-]+)", payload_str):
                            if s not in sediment_ids:
                                sediment_ids.append(s)

                    # Also scan full payload for asset refs (matches chatgpt2api extract_conversation_ids)
                    for fid in file_service_pat.findall(payload_str):
                        if fid not in file_ids and fid != "file_upload":
                            file_ids.append(fid)
                    for s in re.findall(r"sediment://([A-Za-z0-9_-]+)", payload_str):
                        if s not in sediment_ids:
                            sediment_ids.append(s)

                    # Parse JSON to extract upstream metadata signals
                    try:
                        event = json.loads(payload_str)
                    except Exception:
                        event = None

                    if isinstance(event, dict):
                        etype = str(event.get("type") or "")

                        # server_ste_metadata → tells us if image tool was invoked
                        if etype == "server_ste_metadata":
                            meta = event.get("metadata") or {}
                            if isinstance(meta.get("tool_invoked"), bool):
                                tool_invoked = meta["tool_invoked"]
                            turn_use_case = str(meta.get("turn_use_case") or turn_use_case)
                            print(
                                f"[img-debug] SSE server_ste_metadata: tool_invoked={tool_invoked} turn_use_case={turn_use_case!r}",
                                flush=True,
                            )
                            _debug_saw_meta = True
                            # Fast-fail: ChatGPT chose not to generate an image
                            if tool_invoked is False or turn_use_case == "text":
                                print(
                                    "[img-debug] SSE: tool_invoked=false or text reply — account has no image quota, skipping",
                                    flush=True,
                                )
                                return conversation_id, [], [], tool_invoked, turn_use_case, blocked

                        # moderation blocked
                        if etype == "moderation":
                            mod = event.get("moderation_response") or {}
                            if isinstance(mod, dict) and mod.get("blocked") is True:
                                blocked = True
                                print("[img-debug] SSE: content blocked by moderation", flush=True)
                                return conversation_id, [], [], tool_invoked, turn_use_case, blocked

                    # Debug: print first 5 payloads after server_ste_metadata
                    if _debug_saw_meta and _debug_post_meta_count < 5:
                        _debug_post_meta_count += 1
                        print(f"[img-debug] SSE post-meta[{_debug_post_meta_count}] len={len(payload_str)} preview={payload_str[:300]!r}", flush=True)

                    if conversation_id and (file_ids or sediment_ids):
                        return conversation_id, file_ids, sediment_ids, tool_invoked, turn_use_case, blocked

                # If we have conversation_id but no assets for 30s → go poll
                if (
                    cid_at is not None
                    and conversation_id
                    and not file_ids
                    and not sediment_ids
                    and time.monotonic() - cid_at > 30.0
                ):
                    print(
                        "[img-debug] SSE: have conversation_id, no asset refs after 30s — closing stream, will poll",
                        flush=True,
                    )
                    return conversation_id, file_ids, sediment_ids, tool_invoked, turn_use_case, blocked
        finally:
            try:
                response.close()
            except Exception:
                pass
        print(
            f"[img-debug] SSE done: cid={conversation_id!r} file_ids={file_ids} sediment_ids={sediment_ids}"
            f" tool_invoked={tool_invoked} turn_use_case={turn_use_case!r}",
            flush=True,
        )
        return conversation_id, file_ids, sediment_ids, tool_invoked, turn_use_case, blocked

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
            atype = metadata.get("async_task_type")
            if (
                atype is not None
                and str(atype).strip()
                and str(atype).strip() != "image_gen"
            ):
                continue
            file_ids, sediment_ids = [], []
            for part in content.get("parts") or []:
                text = (part.get("asset_pointer") or "") if isinstance(part, dict) else (part if isinstance(part, str) else "")
                file_ids.extend(f for f in file_pat.findall(text) if f not in file_ids)
                sediment_ids.extend(s for s in sed_pat.findall(text) if s not in sediment_ids)
            records.append({"message_id": message_id, "file_ids": file_ids, "sediment_ids": sediment_ids})
        return records

    @staticmethod
    def _fallback_asset_ids_from_conversation_blob(conv: dict) -> tuple[list[str], list[str]]:
        """Last resort: scan serialized conversation for asset URLs (mapping shape may vary)."""
        raw = json.dumps(conv or {}, ensure_ascii=False)
        file_pat = re.compile(r"file-service://([A-Za-z0-9_-]+)")
        sed_pat = re.compile(r"sediment://([A-Za-z0-9_-]+)")
        fids, sids = [], []
        for m in file_pat.findall(raw):
            if m != "file_upload" and m not in fids:
                fids.append(m)
        for m in sed_pat.findall(raw):
            if m not in sids:
                sids.append(m)
        return fids, sids

    @staticmethod
    @staticmethod
    def _check_conversation_quota_error(conv: dict) -> tuple[str, str]:
        """Return (error_msg, restore_at) if conversation indicates quota exhausted.
        Returns ("", "") if no quota error detected.
        """
        mapping = conv.get("mapping") or {}
        restore_at = ""
        for node in mapping.values():
            msg = (node or {}).get("message") or {}
            author = (msg.get("author") or {}).get("role", "")
            content = msg.get("content") or {}
            ctype = content.get("content_type", "")
            # tool message with system_error = quota or backend error
            if author == "tool" and ctype == "system_error":
                return "image generation failed: upstream system_error (quota exhausted or backend error)", restore_at
            # assistant text containing known quota messages
            if author == "assistant" and ctype == "text":
                for part in content.get("parts") or []:
                    text = str(part) if isinstance(part, str) else ""
                    lower = text.lower()
                    if any(kw in lower for kw in (
                        "free plan limit", "hit the free", "limit resets",
                        "image generation limit", "upgrade to", "can't generate",
                        "plan limit for image",
                    )):
                        # Try to extract restore time from message like "resets in 20 hours"
                        msg_preview = text[:200]
                        return f"image generation quota exhausted: {msg_preview}", restore_at
        return "", ""

    def _poll_image_results(self, conversation_id: str, timeout_secs: float = 300.0) -> tuple[list[str], list[str]]:
        start = time.time()
        attempt = 0
        while time.time() - start < timeout_secs:
            attempt += 1
            conv = self._get_conversation(conversation_id)
            # Fast-fail if conversation shows quota exhausted or content blocked
            quota_err, restore_at = self._check_conversation_quota_error(conv)
            if quota_err:
                print(f"[img-debug] poll: quota/error detected → {quota_err[:120]}", flush=True)
                raise ImageQuotaExhaustedError(quota_err, restore_at=restore_at)
            file_ids, sediment_ids = [], []
            for record in self._extract_image_tool_records(conv):
                file_ids.extend(f for f in record["file_ids"] if f not in file_ids)
                sediment_ids.extend(s for s in record["sediment_ids"] if s not in sediment_ids)
            if file_ids:
                return file_ids, sediment_ids
            if sediment_ids:
                return [], sediment_ids
            fb_f, fb_s = self._fallback_asset_ids_from_conversation_blob(conv)
            for f in fb_f:
                if f not in file_ids:
                    file_ids.append(f)
            for s in fb_s:
                if s not in sediment_ids:
                    sediment_ids.append(s)
            if file_ids:
                return file_ids, sediment_ids
            if sediment_ids:
                return [], sediment_ids
            # Debug: dump conversation mapping every time node count changes
            mapping = conv.get("mapping") or {}
            n_nodes = len(mapping)
            if not hasattr(self, '_last_poll_nodes'):
                self._last_poll_nodes = {}
            prev_nodes = self._last_poll_nodes.get(conversation_id, -1)
            if n_nodes != prev_nodes:
                self._last_poll_nodes[conversation_id] = n_nodes
                elapsed = round(time.time() - start)
                print(f"[img-debug] poll t+{elapsed}s attempt={attempt} cid={conversation_id[:8]}… nodes={n_nodes}", flush=True)
                for mid, node in list(mapping.items())[:12]:
                    msg = (node or {}).get("message") or {}
                    author = (msg.get("author") or {}).get("role", "?")
                    atype = (msg.get("metadata") or {}).get("async_task_type", "-")
                    ctype = (msg.get("content") or {}).get("content_type", "-")
                    parts = (msg.get("content") or {}).get("parts") or []
                    part_preview = str(parts[0])[:180] if parts else "-"
                    print(f"[img-debug]   role={author!r} atype={atype!r} ctype={ctype!r} p0={part_preview!r}", flush=True)
            # Dynamic sleep: short at start, slower later
            elapsed = time.time() - start
            if elapsed < 120:
                time.sleep(4)
            elif elapsed < 300:
                time.sleep(8)
            else:
                time.sleep(15)
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
            short = url[:80]
            print(f"[img-debug] CDN download start url={short}...", flush=True)
            last_err: Exception | None = None
            for attempt in range(1, 4):
                try:
                    req = urllib.request.Request(url)
                    if url.startswith(self.BASE_URL):
                        req.add_header("Authorization", f"Bearer {self.access_token}")
                        req.add_header("User-Agent", _browser_user_agent)
                        req.add_header("Referer", self.BASE_URL + "/")
                    resp = self._opener.open(req, timeout=180)
                    try:
                        data = resp.read()
                    finally:
                        resp.close()
                    print(f"[img-debug] CDN download OK bytes={len(data)}", flush=True)
                    images.append(data)
                    break
                except http.client.IncompleteRead as exc:
                    last_err = exc
                    print(f"[img-debug] CDN download attempt {attempt}/3 incomplete: {exc}", flush=True)
                    if attempt >= 3:
                        raise last_err
                except urllib.error.URLError as exc:
                    last_err = exc
                    print(f"[img-debug] CDN download attempt {attempt}/3 URLError: {exc}", flush=True)
                    if attempt >= 3:
                        raise last_err
                except urllib.error.HTTPError:
                    raise
        return images

    def generate_image(self, prompt: str, n: int = 1, size: str | None = None,
                       model: str = "gpt-image-2") -> list[ImageResult]:
        """Generate images via the conversation API.

        Returns a list of ImageResult with base64-encoded image data.
        """
        all_results: list[ImageResult] = []
        enhanced_prompt = _build_image_prompt(prompt, size)

        for index in range(n):
            print(f"[img-debug] step 1/4: bootstrap start token={self.access_token[:20]}...", flush=True)
            self._bootstrap()
            print(f"[img-debug] step 1/4: bootstrap OK", flush=True)

            print(f"[img-debug] step 2/4: chat-requirements start", flush=True)
            requirements = self._get_chat_requirements()
            print(f"[img-debug] step 2/4: chat-requirements OK token_len={len(requirements.token)}", flush=True)

            print(f"[img-debug] step 3/4: prepare start model={model}", flush=True)
            conduit_token = self._prepare_image_conversation(enhanced_prompt, requirements, model)
            print(f"[img-debug] step 3/4: prepare OK conduit_len={len(conduit_token)}", flush=True)
            if not conduit_token.strip():
                print("[img-debug] WARNING: empty conduit_token — image request may hang upstream", flush=True)

            print(f"[img-debug] step 4/4: start_generation start", flush=True)
            status, sse_response = self._start_image_generation(
                enhanced_prompt, requirements, conduit_token, model
            )
            print(f"[img-debug] step 4/4: start_generation OK status={status}", flush=True)

            conversation_id, file_ids, sediment_ids, tool_invoked, turn_use_case, blocked = (
                self._consume_sse_for_image_metadata(sse_response, max_wall_seconds=60.0)
            )
            # Fast-fail: upstream explicitly said no image tool was called
            if tool_invoked is False or turn_use_case == "text":
                raise ImageQuotaExhaustedError(
                    "image generation rejected by upstream (tool_invoked=false or text-only reply); "
                    "account has no image quota"
                )
            if blocked:
                raise RuntimeError("image generation blocked by content moderation")
            if conversation_id and (file_ids or sediment_ids):
                print("[img-debug] SSE: stopped early (conversation_id + asset refs)", flush=True)
            elif conversation_id:
                print("[img-debug] SSE: stopped on deadline/EOF; will poll conversation if needed", flush=True)

            urls = self.resolve_conversation_image_urls(conversation_id, file_ids, sediment_ids)
            if not urls:
                if tool_invoked is True:
                    # Generation was started (tool_invoked=True) but we timed out waiting.
                    # Don't retry with another account — that would burn another quota slot
                    # for an image that is still being generated in the background.
                    raise ImageGenerationStartedError(
                        f"image generation started (tool_invoked=True) but timed out waiting "
                        f"for result (conversation_id={conversation_id!r}); "
                        "retrying with another account would waste its quota"
                    )
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
