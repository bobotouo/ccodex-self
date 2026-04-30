#!/usr/bin/env python3
"""MCP stdio server for image generation via codex2gpt proxy.

Usage in .opencode.json:
{
  "mcpServers": {
    "image-gen": {
      "type": "stdio",
      "command": "python3",
      "args": ["/path/to/scripts/mcp_image_gen.py"],
      "env": {
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
import time
import urllib.request
import urllib.error

PROXY_URL = os.environ.get("IMAGE_GEN_URL", "http://localhost:8080")
API_KEY = os.environ.get("IMAGE_GEN_API_KEY", "")
SAVE_DIR = os.environ.get("IMAGE_SAVE_DIR", os.path.expanduser("~/generated_images"))

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


def call_proxy(prompt, n=1, size="1024x1024"):
    url = f"{PROXY_URL.rstrip('/')}/v1/images/generations"
    payload = json.dumps({
        "prompt": prompt,
        "n": n,
        "size": size,
        "model": "gpt-image-2",
        "response_format": "b64_json",
    }).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))


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
    except Exception as exc:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32000, "message": f"Proxy error: {exc}"},
        }

    saved = []
    for idx, item in enumerate(result.get("data") or []):
        b64 = str(item.get("b64_json") or "")
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
