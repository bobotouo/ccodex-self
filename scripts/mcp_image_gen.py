#!/usr/bin/env python3
"""MCP stdio server for image generation via codex2gpt proxy.

Usage in opencode.jsonc:
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "image-gen": {
      "type": "local",
      "command": ["python3", "/path/to/scripts/mcp_image_gen.py"],
      "enabled": true,
      "environment": {
        "IMAGE_GEN_URL": "http://localhost:8080",
        "IMAGE_GEN_API_KEY": "your-api-key",
        "IMAGE_SAVE_DIR": "/tmp/generated_images"
      }
    }
  }
}
"""

import base64
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

PROXY_URL = os.environ.get("IMAGE_GEN_URL", "http://localhost:8080")
API_KEY = os.environ.get("IMAGE_GEN_API_KEY", "")
SAVE_DIR = os.environ.get("IMAGE_SAVE_DIR", os.path.expanduser("~/generated_images"))
# 整次 HTTP 等待上限（秒）。复杂竖版 + 长文案常需数分钟；须 ≤ opencode 的 MCP 超时
HTTP_TIMEOUT_SEC = max(60, int(os.environ.get("IMAGE_GEN_HTTP_TIMEOUT_SEC", "900")))

TOOL_DEF = {
    "name": "generate_image",
    "description": (
        "Generate an image from a text prompt. "
        "Saves the image locally and returns the file path."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The text prompt describing the image to generate",
            },
            "n": {
                "type": "integer",
                "description": "Number of images to generate (1-4, default 1)",
                "default": 1,
            },
            "size": {
                "type": "string",
                "description": "Image size: 1024x1024, 1024x1792, 1792x1024",
                "default": "1024x1024",
            },
            "filename": {
                "type": "string",
                "description": "Filename to save as (without extension). Defaults to timestamp.",
            },
        },
        "required": ["prompt"],
    },
}


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def send_response(resp):
    line = json.dumps(resp, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def save_image(b64_data, filename=None):
    os.makedirs(SAVE_DIR, exist_ok=True)
    if not filename:
        filename = f"img_{int(time.time())}_{os.getpid()}"
    if not filename.endswith(".png"):
        filename += ".png"
    filepath = os.path.join(SAVE_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(base64.b64decode(b64_data))
    return filepath


def call_proxy(prompt, n=1, size="1024x1024", model="gpt-image-2"):
    base = PROXY_URL.rstrip("/")
    if base.endswith("/v1"):
        url = f"{base}/images/generations"
    else:
        url = f"{base}/v1/images/generations"
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "n": n,
        "size": size,
        "response_format": "b64_json",
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    result = {}

    def _do():
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SEC) as resp:
                result["ok"] = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            result["err"] = e

    log(
        f"已向代理请求生图（HTTP 最长等待 {HTTP_TIMEOUT_SEC}s）。"
        "复杂竖版海报可能要几分钟——此期间 MCP 会阻塞直到完成。"
    )
    t = threading.Thread(target=_do, daemon=True)
    t.start()
    start = time.time()
    while t.is_alive():
        t.join(timeout=30)
        if t.is_alive():
            elapsed = int(time.time() - start)
            log(f"仍在等待代理返回… {elapsed}s / http_timeout={HTTP_TIMEOUT_SEC}s")
    if "err" in result:
        raise result["err"]
    return result["ok"]


def handle_generate_image(request_id, arguments):
    prompt = str(arguments.get("prompt") or "").strip()
    if not prompt:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32602, "message": "prompt is required"},
        }

    n = max(1, min(4, int(arguments.get("n") or 1)))
    size = str(arguments.get("size") or "1024x1024")
    filename = str(arguments.get("filename") or "").strip() or None

    try:
        result = call_proxy(prompt, n=n, size=size)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": f"HTTP Error {exc.code}: {exc.reason}. {body}".strip()},
        }
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": f"Proxy error: {exc}"},
        }

    # Parse b64_json from /v1/images/generations response
    data_list = result.get("data") or []

    saved = []
    for idx, item in enumerate(data_list):
        b64 = item.get("b64_json") or ""
        if not b64:
            continue
        if n > 1 and filename:
            base, ext = os.path.splitext(filename)
            fname = f"{base}_{idx + 1}{ext}"
        elif filename:
            fname = filename
        else:
            fname = None
        filepath = save_image(b64, fname)
        saved.append(filepath)

    if saved:
        text = "Image generated and saved:\n" + "\n".join(saved)
    else:
        text = "Image generation completed but no data returned."

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {
            "content": [{"type": "text", "text": text}],
            "isError": False,
        },
    }


def handle_message(body):
    method = body.get("method")
    request_id = body.get("id")
    params = body.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "codex2gpt-image-gen", "version": "1.0.0"},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"tools": [TOOL_DEF]},
        }

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        if tool_name != "generate_image":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": f"Unknown tool: {tool_name}"},
            }
        return handle_generate_image(request_id, arguments)

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main():
    log(f"MCP image-gen server started. Proxy: {PROXY_URL}, Save dir: {SAVE_DIR}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            body = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle_message(body)
        if response is not None:
            send_response(response)


if __name__ == "__main__":
    main()
