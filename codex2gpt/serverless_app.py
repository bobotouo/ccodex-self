"""Vercel serverless entrypoint (phase-1 migration)."""

from __future__ import annotations

import datetime
import os
import secrets
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

import app as legacy


app = FastAPI(title="codex2gpt-serverless")


def _client_ip(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "")


def _dashboard_authenticated(request: Request) -> bool:
    client_ip = _client_ip(request)
    if legacy.is_local_request(client_ip) and legacy.DASHBOARD_LOCAL_BYPASS and not legacy.DASHBOARD_FORCE_LOGIN:
        return True
    if not legacy.dashboard_login_required():
        return True
    session_id = request.cookies.get(legacy.DASHBOARD_SESSION_COOKIE, "").strip()
    if not session_id:
        return False
    legacy.STATE_DB.cleanup_expired_dashboard_sessions()
    return legacy.STATE_DB.validate_dashboard_session(session_id)


def _require_dashboard(request: Request) -> JSONResponse | None:
    if _dashboard_authenticated(request):
        return None
    return JSONResponse(
        status_code=401,
        content={"error": {"type": "authentication_error", "message": "dashboard login required"}},
    )


def _set_dashboard_cookie(response: JSONResponse, session_id: str) -> None:
    max_age = max(60, legacy.DASHBOARD_SESSION_TTL)
    response.set_cookie(
        key=legacy.DASHBOARD_SESSION_COOKIE,
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
        "migration_phase": 1,
        "message": "Dashboard/auth APIs are migrated first; proxy APIs are in progress.",
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
    index_path = f"{legacy.WEB_DIR}/index.html"
    return FileResponse(index_path, media_type="text/html")


@app.post("/auth/login")
async def auth_login(request: Request):
    payload = await request.json()
    password = str((payload or {}).get("password") or "")
    secret = legacy.dashboard_secret()
    if legacy.dashboard_login_required() and not secret:
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
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=max(60, legacy.DASHBOARD_SESSION_TTL))
    ).isoformat(timespec="seconds")
    legacy.STATE_DB.create_dashboard_session(session_id, expires_at=expires_at, remote_addr=_client_ip(request))
    response = JSONResponse(status_code=200, content={"ok": True})
    _set_dashboard_cookie(response, session_id)
    return response


@app.delete("/auth/login")
def auth_logout(request: Request):
    session_id = request.cookies.get(legacy.DASHBOARD_SESSION_COOKIE, "").strip()
    if session_id:
        legacy.STATE_DB.delete_dashboard_session(session_id)
    response = JSONResponse(status_code=200, content={"ok": True})
    response.delete_cookie(legacy.DASHBOARD_SESSION_COOKIE, path="/")
    return response


@app.get("/auth/status")
def auth_status(request: Request):
    legacy.sync_accounts_with_state()
    secret = legacy.dashboard_secret()
    local_bypass_effective = bool(
        legacy.DASHBOARD_LOCAL_BYPASS and not legacy.DASHBOARD_FORCE_LOGIN and legacy.is_local_request(_client_ip(request))
    )
    return {
        "authenticated": _dashboard_authenticated(request),
        "password_required": legacy.dashboard_login_required() and not local_bypass_effective,
        "local_dashboard_bypass": local_bypass_effective,
        "dashboard_force_login": legacy.DASHBOARD_FORCE_LOGIN,
        "dashboard_password_configured": bool(secret),
        "accounts": len(legacy.STATE_DB.list_accounts()),
        "proxies": len(legacy.STATE_DB.list_proxies()),
        "relay_providers": len(legacy.STATE_DB.list_relay_providers(enabled_only=True)),
        "managed_api_keys": len(legacy.STATE_DB.list_api_keys(enabled_only=True)),
        "api_key_required": bool(legacy.API_KEY_REQUIRED or legacy.API_KEY or legacy.STATE_DB.list_api_keys(enabled_only=True)),
        "rotation_mode": legacy.current_rotation_mode(),
        "responses_transport": legacy.current_responses_transport_mode(),
    }


@app.get("/{asset_name:path}")
def web_assets(asset_name: str):
    if asset_name.startswith("assets/") or asset_name.endswith(".js") or asset_name.endswith(".css"):
        file_path = os.path.join(legacy.WEB_DIR, asset_name)
        if os.path.isfile(file_path):
            if asset_name.endswith(".js"):
                media_type = "application/javascript; charset=utf-8"
            elif asset_name.endswith(".css"):
                media_type = "text/css; charset=utf-8"
            else:
                media_type = None
            return FileResponse(file_path, media_type=media_type)
    return not_yet_migrated(asset_name)


@app.get("/admin/api-keys")
def list_api_keys(request: Request, hours: int | None = None):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    return legacy.STATE_DB.get_api_key_usage_summary(hours=hours)


@app.post("/admin/api-keys")
async def create_api_key(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    payload = await request.json()
    name = str((payload or {}).get("name") or "").strip() or "default"
    key_id = secrets.token_hex(8)
    raw_key = f"c2g_{secrets.token_urlsafe(24)}"
    record = legacy.STATE_DB.upsert_api_key(
        key_id,
        name=name,
        api_key=raw_key,
        key_hash=legacy.hash_api_key(raw_key),
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
    legacy.STATE_DB.delete_api_key(key_id)
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

