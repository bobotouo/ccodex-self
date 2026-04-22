"""Vercel serverless entrypoint with DB-backed state."""

from __future__ import annotations

import datetime
import base64
import hashlib
import json
import os
import secrets
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from codex2gpt.serverless_state import ServerlessStateStore


app = FastAPI(title="codex2gpt-serverless")
STATE_DB = ServerlessStateStore()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WEB_DIR = os.path.abspath(os.environ.get("LITE_WEB_DIR", os.path.join(BASE_DIR, "web")))
DASHBOARD_PASSWORD = os.environ.get("LITE_DASHBOARD_PASSWORD", "").strip()
DASHBOARD_SESSION_COOKIE = os.environ.get("LITE_DASHBOARD_SESSION_COOKIE", "codex2gpt_dashboard_session").strip() or "codex2gpt_dashboard_session"
DASHBOARD_SESSION_TTL = int(os.environ.get("LITE_DASHBOARD_SESSION_TTL", "43200") or "43200")
DASHBOARD_FORCE_LOGIN = os.environ.get("LITE_DASHBOARD_FORCE_LOGIN", "0").strip().lower() in {"1", "true", "yes", "on"}
DASHBOARD_LOCAL_BYPASS = os.environ.get("LITE_DASHBOARD_LOCAL_BYPASS", "1").strip().lower() in {"1", "true", "yes", "on"}
API_KEY = os.environ.get("LITE_API_KEY", "")
API_KEY_REQUIRED = os.environ.get("LITE_API_KEY_REQUIRED", "0").strip().lower() in {"1", "true", "yes", "on"}


def is_local_request(client_ip: str) -> bool:
    value = str(client_ip or "").strip().lower()
    return value in {"127.0.0.1", "::1", "localhost"}


def dashboard_secret() -> str:
    return DASHBOARD_PASSWORD or API_KEY


def dashboard_login_required() -> bool:
    return bool(DASHBOARD_FORCE_LOGIN or dashboard_secret())


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(str(raw_key or "").encode("utf-8")).hexdigest()


def decode_jwt_payload(token: str) -> dict[str, Any]:
    if not isinstance(token, str) or token.count(".") < 2:
        return {}
    payload = token.split(".")[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode((payload + padding).encode("ascii"))
        value = json.loads(decoded.decode("utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "")


def _dashboard_authenticated(request: Request) -> bool:
    client_ip = _client_ip(request)
    if is_local_request(client_ip) and DASHBOARD_LOCAL_BYPASS and not DASHBOARD_FORCE_LOGIN:
        return True
    if not dashboard_login_required():
        return True
    session_id = request.cookies.get(DASHBOARD_SESSION_COOKIE, "").strip()
    if not session_id:
        return False
    STATE_DB.cleanup_expired_dashboard_sessions()
    return STATE_DB.validate_dashboard_session(session_id)


def _require_dashboard(request: Request) -> JSONResponse | None:
    if _dashboard_authenticated(request):
        return None
    return JSONResponse(
        status_code=401,
        content={"error": {"type": "authentication_error", "message": "dashboard login required"}},
    )


def _set_dashboard_cookie(response: JSONResponse, session_id: str) -> None:
    max_age = max(60, DASHBOARD_SESSION_TTL)
    response.set_cookie(
        key=DASHBOARD_SESSION_COOKIE,
        value=session_id,
        max_age=max_age,
        path="/",
        httponly=True,
        samesite="lax",
    )


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "mode": "serverless",
        "migration_phase": 2,
        "state_backend": STATE_DB.backend,
        "message": "Dashboard/auth APIs are DB-backed; proxy APIs are in progress.",
    }


@app.get("/")
def root(request: Request):
    if not _dashboard_authenticated(request):
        return HTMLResponse(
            """
            <!doctype html>
            <html lang="zh-CN">
              <head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>登录</title></head>
              <body style="font-family:-apple-system,Segoe UI,Arial;padding:24px">
                <h2>Codex2gpt Dashboard 登录</h2>
                <form id="login">
                  <input type="password" id="pwd" placeholder="请输入密码" style="padding:8px;min-width:280px"/>
                  <button type="submit">登录</button>
                  <p id="msg" style="color:#d33"></p>
                </form>
                <script>
                  document.getElementById("login").addEventListener("submit", async (e) => {
                    e.preventDefault();
                    const password = document.getElementById("pwd").value || "";
                    const res = await fetch("/auth/login", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      credentials: "same-origin",
                      body: JSON.stringify({ password })
                    });
                    if (res.ok) { location.href = "/"; return; }
                    document.getElementById("msg").textContent = "登录失败，请检查密码";
                  });
                </script>
              </body>
            </html>
            """
        )
    index_path = os.path.join(WEB_DIR, "index.html")
    return FileResponse(index_path, media_type="text/html")


@app.post("/auth/login")
async def auth_login(request: Request):
    payload = await request.json()
    password = str((payload or {}).get("password") or "")
    secret = dashboard_secret()
    if dashboard_login_required() and not secret:
        return JSONResponse(
            status_code=400,
            content={"error": {"type": "configuration_error", "message": "dashboard password is not configured"}},
        )
    if secret and password != secret:
        return JSONResponse(
            status_code=401,
            content={"error": {"type": "authentication_error", "message": "invalid dashboard password"}},
        )
    session_id = secrets.token_urlsafe(24)
    expires_at = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=max(60, DASHBOARD_SESSION_TTL))
    ).isoformat(timespec="seconds")
    STATE_DB.create_dashboard_session(session_id, expires_at=expires_at, remote_addr=_client_ip(request))
    response = JSONResponse(status_code=200, content={"ok": True})
    _set_dashboard_cookie(response, session_id)
    return response


@app.delete("/auth/login")
def auth_logout(request: Request):
    session_id = request.cookies.get(DASHBOARD_SESSION_COOKIE, "").strip()
    if session_id:
        STATE_DB.delete_dashboard_session(session_id)
    response = JSONResponse(status_code=200, content={"ok": True})
    response.delete_cookie(DASHBOARD_SESSION_COOKIE, path="/")
    return response


@app.get("/auth/status")
def auth_status(request: Request):
    secret = dashboard_secret()
    local_bypass_effective = bool(
        DASHBOARD_LOCAL_BYPASS and not DASHBOARD_FORCE_LOGIN and is_local_request(_client_ip(request))
    )
    return {
        "authenticated": _dashboard_authenticated(request),
        "password_required": dashboard_login_required() and not local_bypass_effective,
        "local_dashboard_bypass": local_bypass_effective,
        "dashboard_force_login": DASHBOARD_FORCE_LOGIN,
        "dashboard_password_configured": bool(secret),
        "accounts": len(STATE_DB.list_accounts()),
        "proxies": len(STATE_DB.list_proxies()),
        "relay_providers": len(STATE_DB.list_relay_providers(enabled_only=True)),
        "managed_api_keys": len(STATE_DB.list_api_keys(enabled_only=True)),
        "api_key_required": bool(API_KEY_REQUIRED or API_KEY or STATE_DB.list_api_keys(enabled_only=True)),
        "rotation_mode": "least_used",
        "responses_transport": "auto",
    }


@app.get("/auth/accounts")
def auth_accounts(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    accounts = []
    for account in STATE_DB.list_accounts():
        item = dict(account)
        item["proxy_mode"] = "global"
        item["proxy_assignment"] = None
        item["is_codex_app_current"] = False
        item["is_codex_app_reserved"] = False
        accounts.append(item)
    return {
        "data": accounts,
        "codex_app": {
            "matched": False,
            "current_entry_id": "",
            "current_account_id": "",
            "current_identity_key": "",
            "auth_path": os.environ.get("LITE_CODEX_AUTH_PATH", "~/.codex/auth.json"),
            "external_override_detected": False,
        },
        "warnings": [],
        "proxy_assignments": [],
        "quota_refresh": None,
    }


@app.post("/admin/accounts/import-local")
def import_local_accounts(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    auth_dir = os.path.abspath(os.environ.get("LITE_AUTH_DIR", "/tmp/codex2gpt-runtime/accounts"))
    imported: list[str] = []
    if not os.path.isdir(auth_dir):
        return {"imported": imported, "count": 0, "auth_dir": auth_dir}
    for name in sorted(os.listdir(auth_dir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(auth_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            continue
        tokens = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else {}
        id_claims = decode_jwt_payload(str(tokens.get("id_token") or ""))
        auth_claims = id_claims.get("https://api.openai.com/auth") if isinstance(id_claims.get("https://api.openai.com/auth"), dict) else {}
        profile = id_claims.get("https://api.openai.com/profile") if isinstance(id_claims.get("https://api.openai.com/profile"), dict) else {}
        entry_id = os.path.basename(path)
        email = str(payload.get("email") or id_claims.get("email") or profile.get("email") or "").strip()
        user_id = str(payload.get("user_id") or id_claims.get("sub") or auth_claims.get("user_id") or "").strip()
        account_id = str(tokens.get("account_id") or payload.get("account_id") or auth_claims.get("chatgpt_account_id") or "").strip()
        plan_type = str(payload.get("plan_type") or payload.get("plan") or auth_claims.get("chatgpt_plan_type") or "").strip()
        STATE_DB.upsert_account(
            entry_id,
            auth_file=path,
            email=email,
            user_id=user_id,
            account_id=account_id,
            plan_type=plan_type,
            status="active",
            refresh_token=str(tokens.get("refresh_token") or ""),
            proxy_id=None,
            last_error=None,
            metadata={"source": "local_import", "id_claims": id_claims},
            quota={},
            usage={"input_tokens": 0, "output_tokens": 0, "request_count": 0},
            auth_payload=payload,
        )
        imported.append(entry_id)
    return {"imported": imported, "count": len(imported), "auth_dir": auth_dir}


@app.get("/app.js")
def web_app_js():
    file_path = os.path.join(WEB_DIR, "app.js")
    if os.path.isfile(file_path):
        return FileResponse(file_path, media_type="application/javascript; charset=utf-8")
    return JSONResponse(status_code=404, content={"error": {"type": "not_found", "message": "asset not found"}})


@app.get("/styles.css")
def web_styles_css():
    file_path = os.path.join(WEB_DIR, "styles.css")
    if os.path.isfile(file_path):
        return FileResponse(file_path, media_type="text/css; charset=utf-8")
    return JSONResponse(status_code=404, content={"error": {"type": "not_found", "message": "asset not found"}})


@app.get("/assets/{asset_path:path}")
def web_assets(asset_path: str):
    file_path = os.path.join(WEB_DIR, "assets", asset_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    return JSONResponse(status_code=404, content={"error": {"type": "not_found", "message": "asset not found"}})


@app.get("/admin/api-keys")
def list_api_keys(request: Request, hours: int | None = None):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    return STATE_DB.get_api_key_usage_summary(hours=hours)


@app.post("/admin/api-keys")
async def create_api_key(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    payload = await request.json()
    name = str((payload or {}).get("name") or "").strip() or "default"
    key_id = secrets.token_hex(8)
    raw_key = f"c2g_{secrets.token_urlsafe(24)}"
    record = STATE_DB.upsert_api_key(
        key_id,
        name=name,
        api_key=raw_key,
        key_hash=hash_api_key(raw_key),
        key_prefix=raw_key[:10],
        enabled=True,
        metadata={"created_by": _client_ip(request), "source": "serverless"},
    )
    return {
        "key": raw_key,
        "record": {
            "key_id": record.get("key_id"),
            "name": record.get("name"),
            "key_prefix": record.get("key_prefix"),
            "enabled": record.get("enabled"),
            "created_at": record.get("created_at"),
        },
    }


@app.delete("/admin/api-keys/{key_id}")
def delete_api_key(key_id: str, request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    STATE_DB.delete_api_key(key_id)
    return {"deleted": True, "key_id": key_id}

@app.api_route("/{path:path}", methods=["POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def not_yet_migrated(path: str):
    return JSONResponse(
        status_code=501,
        content={
            "error": {
                "type": "not_implemented",
                "message": "This route is not migrated to serverless yet.",
                "path": f"/{path}",
            }
        },
    )

