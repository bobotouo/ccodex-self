"""Vercel serverless entrypoint with DB-backed state."""

from __future__ import annotations

import datetime
import base64
import hashlib
import io
import json
import os
import queue
import secrets
import threading
import time
import urllib.parse
import urllib.request
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse

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
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
TOKEN_URL = "https://auth.openai.com/oauth/token"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
OAUTH_CALLBACK_TTL_SECONDS = int(os.environ.get("LITE_OAUTH_CALLBACK_TTL_SECONDS", "300") or "300")
LEGACY_SYNC_INTERVAL_MS = int(os.environ.get("LITE_LEGACY_SYNC_INTERVAL_MS", "800") or "800")
CONNECTOR_SESSION_TTL_SECONDS = int(os.environ.get("LITE_CONNECTOR_SESSION_TTL_SECONDS", "600") or "600")

# Keep legacy runtime artifacts writable in serverless environment.
os.environ.setdefault("LITE_RUNTIME_ROOT", "/tmp/codex2gpt-runtime")
os.environ.setdefault("LITE_AUTH_DIR", "/tmp/codex2gpt-runtime/accounts")
os.environ.setdefault("LITE_STATE_DB", "/tmp/codex2gpt-runtime/state.sqlite3")
os.environ.setdefault("LITE_COOKIES_PATH", "/tmp/codex2gpt-runtime/cookies.json")
os.environ.setdefault("LITE_SETTINGS_PATH", "/tmp/codex2gpt-runtime/settings.json")
os.environ.setdefault("LITE_FINGERPRINT_CACHE_PATH", "/tmp/codex2gpt-runtime/fingerprint-cache.json")

import app as legacy

# 与 import app 时创建的 legacy.STATE_DB 解耦，否则记用量/刷账号走「桥接」的 sqlite、读显式 /admin 走另一份，控制台永远 0/无数据。
# - 仅本机 state.sqlite3：与 Serverless 内嵌的 RuntimeStateStore 共享同一对象。
# - 已设 DATABASE_URL：让 legacy 与 ServerlessStateStore 为同一对象（含 PG + aux sqlite，见 serverless_state）。
if getattr(STATE_DB, "_sqlite", None) is not None:
    legacy.STATE_DB = STATE_DB._sqlite
elif getattr(STATE_DB, "backend", None) == "postgres":
    legacy.STATE_DB = STATE_DB

_LEGACY_SYNC_LOCK = threading.RLock()
_LEGACY_LAST_SYNC_MONO = 0.0
_LEGACY_LAST_SYNC_ERROR = ""


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


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _iso_after_seconds(seconds: int) -> str:
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=max(1, int(seconds)))).isoformat(timespec="seconds")


def _parse_iso(value: str) -> datetime.datetime | None:
    try:
        parsed = datetime.datetime.fromisoformat(str(value or ""))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed.astimezone(datetime.timezone.utc)


def _persist_auth_payload(payload: dict[str, Any], *, source: str, entry_id_override: str = "") -> dict[str, Any]:
    tokens = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else {}
    id_claims = decode_jwt_payload(str(tokens.get("id_token") or ""))
    auth_claims = id_claims.get("https://api.openai.com/auth") if isinstance(id_claims.get("https://api.openai.com/auth"), dict) else {}
    profile = id_claims.get("https://api.openai.com/profile") if isinstance(id_claims.get("https://api.openai.com/profile"), dict) else {}

    entry_id = os.path.basename(entry_id_override or str(payload.get("entry_id") or "")).strip()
    if not entry_id:
        raw_email = str(payload.get("email") or id_claims.get("email") or profile.get("email") or "").strip() or "account"
        safe_email = "".join(ch if ch.isalnum() or ch in {"_", "-", "."} else "_" for ch in raw_email)
        entry_id = f"{safe_email}_{secrets.token_hex(6)}.json"
    if not entry_id.endswith(".json"):
        entry_id = f"{entry_id}.json"

    email = str(payload.get("email") or id_claims.get("email") or profile.get("email") or "").strip()
    user_id = str(payload.get("user_id") or id_claims.get("sub") or auth_claims.get("user_id") or "").strip()
    account_id = str(tokens.get("account_id") or payload.get("account_id") or auth_claims.get("chatgpt_account_id") or "").strip()
    plan_type = str(payload.get("plan_type") or payload.get("plan") or auth_claims.get("chatgpt_plan_type") or "").strip()

    STATE_DB.upsert_account(
        entry_id,
        auth_file=f"db://accounts/{entry_id}",
        email=email,
        user_id=user_id,
        account_id=account_id,
        plan_type=plan_type,
        status="active",
        refresh_token=str(tokens.get("refresh_token") or ""),
        proxy_id=None,
        last_error=None,
        metadata={"source": source, "id_claims": id_claims},
        quota={},
        usage={"input_tokens": 0, "output_tokens": 0, "request_count": 0},
        auth_payload=payload,
    )
    return {"entry_id": entry_id, "email": email}


def _find_existing_account_entry(payload: dict[str, Any]) -> str:
    tokens = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else {}
    refresh_token = str(tokens.get("refresh_token") or "").strip()
    id_claims = decode_jwt_payload(str(tokens.get("id_token") or ""))
    auth_claims = id_claims.get("https://api.openai.com/auth") if isinstance(id_claims.get("https://api.openai.com/auth"), dict) else {}
    profile = id_claims.get("https://api.openai.com/profile") if isinstance(id_claims.get("https://api.openai.com/profile"), dict) else {}
    user_id = str(payload.get("user_id") or id_claims.get("sub") or auth_claims.get("user_id") or "").strip()
    account_id = str(tokens.get("account_id") or payload.get("account_id") or auth_claims.get("chatgpt_account_id") or "").strip()
    email = str(payload.get("email") or id_claims.get("email") or profile.get("email") or "").strip().lower()

    for account in STATE_DB.list_accounts():
        if not isinstance(account, dict):
            continue
        account_user_id = str(account.get("user_id") or "").strip()
        account_account_id = str(account.get("account_id") or "").strip()
        account_email = str(account.get("email") or "").strip().lower()
        account_payload = account.get("auth_payload") if isinstance(account.get("auth_payload"), dict) else {}
        account_tokens = account_payload.get("tokens") if isinstance(account_payload.get("tokens"), dict) else {}
        account_refresh = str(account_tokens.get("refresh_token") or "").strip()
        if refresh_token and account_refresh and refresh_token == account_refresh:
            return str(account.get("entry_id") or "")
        if user_id and account_user_id and user_id == account_user_id:
            return str(account.get("entry_id") or "")
        if account_id and account_account_id and account_id == account_account_id:
            return str(account.get("entry_id") or "")
        if email and account_email and email == account_email:
            return str(account.get("entry_id") or "")
    return ""


def oauth_redirect_uri_for_request(request: Request) -> str:
    public_base = (os.environ.get("LITE_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not public_base:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        proto = request.headers.get("x-forwarded-proto") or "https"
        public_base = f"{proto}://{host}".rstrip("/")
    return f"{public_base}/auth/callback"


def oauth_session_expired(created_at: str) -> bool:
    if not created_at:
        return True
    try:
        created = datetime.datetime.fromisoformat(created_at)
    except ValueError:
        return True
    if created.tzinfo is None:
        created = created.replace(tzinfo=datetime.timezone.utc)
    age = (datetime.datetime.now(datetime.timezone.utc) - created.astimezone(datetime.timezone.utc)).total_seconds()
    return age > max(60, OAUTH_CALLBACK_TTL_SECONDS)


def oauth_callback_result_html(success: bool, title: str, message: str) -> str:
    event_type = "oauth-callback-success" if success else "oauth-callback-error"
    payload = {"type": event_type}
    if not success:
        payload["error"] = str(message)
    script = [
        "<script>",
        "(function(){",
        f"var payload = {json.dumps(payload, ensure_ascii=False)};",
        "try { if (window.opener) { window.opener.postMessage(payload, '*'); } } catch (err) {}",
    ]
    if success:
        script.append("setTimeout(function(){ try { window.close(); } catch (err) {} }, 600);")
    script.extend(["})();", "</script>"])
    accent = "#1f8f5f" if success else "#b34040"
    safe_message = (
        str(message or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{'Login Successful' if success else 'Login Failed'}</title>
    <style>
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        background: linear-gradient(180deg, #f6faf7, #e8efe7);
        color: #183126;
      }}
      .card {{
        width: min(560px, calc(100% - 32px));
        padding: 28px;
        border-radius: 24px;
        background: rgba(255, 255, 255, 0.94);
        border: 1px solid rgba(24, 49, 38, 0.1);
        box-shadow: 0 18px 50px rgba(24, 49, 38, 0.08);
      }}
      h1 {{ margin: 0 0 10px; color: {accent}; font-size: 1.6rem; }}
      p {{ margin: 0; line-height: 1.55; white-space: pre-wrap; word-break: break-word; }}
    </style>
  </head>
  <body>
    <article class="card">
      <h1>{title}</h1>
      <p>{safe_message}</p>
    </article>
    {''.join(script)}
  </body>
</html>"""


def _sync_db_accounts_to_legacy_runtime() -> None:
    os.makedirs(legacy.AUTH_DIR, exist_ok=True)
    seen: set[str] = set()
    for account in STATE_DB.list_accounts():
        entry_id = os.path.basename(str(account.get("entry_id") or "")).strip()
        payload = account.get("auth_payload")
        if not isinstance(payload, dict) or not payload:
            refresh_token = str(account.get("refresh_token") or "").strip()
            if refresh_token:
                # Older PG upsert logic could wipe auth_payload_json while leaving refresh_token.
                # Rebuild enough auth JSON for OAuthAccount.access_token() to refresh a new access token.
                payload = {
                    "auth_mode": "chatgpt",
                    "email": str(account.get("email") or ""),
                    "user_id": str(account.get("user_id") or ""),
                    "account_id": str(account.get("account_id") or ""),
                    "plan_type": str(account.get("plan_type") or ""),
                    "tokens": {
                        "refresh_token": refresh_token,
                        "account_id": str(account.get("account_id") or ""),
                    },
                    "last_refresh": str(account.get("updated_at") or ""),
                }
                STATE_DB.upsert_account(entry_id, auth_payload=payload)
        if not entry_id or not isinstance(payload, dict) or not payload:
            continue
        target = os.path.join(legacy.AUTH_DIR, entry_id)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        seen.add(entry_id)
    for name in os.listdir(legacy.AUTH_DIR):
        if not name.endswith(".json"):
            continue
        if name not in seen:
            try:
                os.remove(os.path.join(legacy.AUTH_DIR, name))
            except Exception:
                pass
    legacy.pool.reload()
    legacy.sync_accounts_with_state()


def _sync_api_keys_to_legacy_state() -> None:
    try:
        pg_keys = STATE_DB.list_api_keys(enabled_only=False)
        legacy_keys = {item.get("key_id"): item for item in legacy.STATE_DB.list_api_keys(enabled_only=False)}
        pg_ids: set[str] = set()
        for item in pg_keys:
            key_id = str(item.get("key_id") or "").strip()
            if not key_id:
                continue
            pg_ids.add(key_id)
            legacy.STATE_DB.upsert_api_key(
                key_id,
                name=str(item.get("name") or key_id),
                api_key=str(item.get("api_key") or ""),
                key_hash=str(item.get("key_hash") or ""),
                key_prefix=str(item.get("key_prefix") or ""),
                enabled=bool(item.get("enabled")),
                metadata=item.get("metadata") if isinstance(item.get("metadata"), dict) else {},
            )
        for key_id in legacy_keys:
            if key_id and key_id not in pg_ids:
                legacy.STATE_DB.delete_api_key(str(key_id))
    except Exception:
        pass


def _mirror_session_to_legacy(session_id: str, remote_addr: str = "") -> None:
    if not session_id:
        return
    if not STATE_DB.validate_dashboard_session(session_id):
        return
    expires_at = (
        datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=max(60, DASHBOARD_SESSION_TTL))
    ).isoformat(timespec="seconds")
    try:
        legacy.STATE_DB.create_dashboard_session(
            session_id,
            expires_at=expires_at,
            remote_addr=remote_addr,
            created_at=now_iso(),
        )
    except Exception:
        pass


def _sync_legacy_runtime_state(*, session_id: str = "", remote_addr: str = "", force: bool = False) -> None:
    """Best-effort sync for all bridge-dependent legacy state.

    This reduces drift between serverless DB-backed state and legacy runtime state.
    """
    global _LEGACY_LAST_SYNC_MONO, _LEGACY_LAST_SYNC_ERROR
    now_mono = time.monotonic()
    if not force and (now_mono - _LEGACY_LAST_SYNC_MONO) * 1000 < max(0, LEGACY_SYNC_INTERVAL_MS):
        if session_id:
            _mirror_session_to_legacy(session_id, remote_addr)
        return
    with _LEGACY_SYNC_LOCK:
        now_mono = time.monotonic()
        if not force and (now_mono - _LEGACY_LAST_SYNC_MONO) * 1000 < max(0, LEGACY_SYNC_INTERVAL_MS):
            if session_id:
                _mirror_session_to_legacy(session_id, remote_addr)
            return
        try:
            _sync_db_accounts_to_legacy_runtime()
            _sync_api_keys_to_legacy_state()
            if session_id:
                _mirror_session_to_legacy(session_id, remote_addr)
            _LEGACY_LAST_SYNC_ERROR = ""
        except Exception as exc:  # pragma: no cover
            _LEGACY_LAST_SYNC_ERROR = str(exc)
        finally:
            _LEGACY_LAST_SYNC_MONO = time.monotonic()


class _CaseHeaders:
    def __init__(self, source: dict[str, str]):
        self._data = {str(k).lower(): str(v) for k, v in source.items()}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(str(key).lower(), default)

    def items(self):
        return self._data.items()


class _LegacyBridgeHandler(legacy.Handler):
    def __init__(self, method: str, path: str, headers: dict[str, str], body: bytes, client_ip: str, *, wfile=None):
        self.command = method.upper()
        self.path = path
        self.request_version = "HTTP/1.1"
        self.client_address = (client_ip or "127.0.0.1", 0)
        self.headers = _CaseHeaders(headers)
        self.rfile = io.BytesIO(body or b"")
        self.wfile = wfile if wfile is not None else io.BytesIO()
        self.server = None
        self.close_connection = True
        self._status = 200
        self._response_headers: list[tuple[str, str]] = []
        self._ended = False
        self.headers_ready = threading.Event()
        self._reset_request_tracking()

    def send_response(self, code, message=None):  # type: ignore[override]
        self._status = int(code)

    def send_header(self, keyword, value):  # type: ignore[override]
        self._response_headers.append((str(keyword), str(value)))

    def end_headers(self):  # type: ignore[override]
        self._ended = True
        self.headers_ready.set()

    def log_message(self, fmt, *args):  # type: ignore[override]
        return

    @property
    def response_status(self) -> int:
        return self._status

    @property
    def response_headers(self) -> list[tuple[str, str]]:
        return list(self._response_headers)

    @property
    def response_body(self) -> bytes:
        return self.wfile.getvalue()


class _StreamSink:
    def __init__(self):
        self._queue: queue.Queue[bytes | None] = queue.Queue()

    def write(self, data):  # type: ignore[override]
        if not data:
            return 0
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._queue.put(bytes(data))
        return len(data)

    def flush(self):  # type: ignore[override]
        return

    def close(self):
        self._queue.put(None)

    def iter_bytes(self):
        while True:
            chunk = self._queue.get()
            if chunk is None:
                break
            yield chunk


def _is_streaming_request(path: str, method: str, body: bytes) -> bool:
    if method.upper() != "POST":
        return False
    if path not in {"/v1/responses", "/v1/chat/completions", "/v1/messages"}:
        return False
    try:
        payload = json.loads((body or b"{}").decode("utf-8"))
    except Exception:
        return False
    return bool(payload.get("stream"))


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
        "legacy_sync_interval_ms": LEGACY_SYNC_INTERVAL_MS,
        "legacy_last_sync_error": _LEGACY_LAST_SYNC_ERROR,
        "message": "Dashboard/auth APIs are DB-backed; proxy APIs are in progress.",
    }


@app.get("/")
def root(request: Request):
    if not _dashboard_authenticated(request):
        return HTMLResponse(
            """
            <!doctype html>
            <html lang="zh-CN">
              <head>
                <meta charset="utf-8" />
                <meta name="viewport" content="width=device-width, initial-scale=1" />
                <title>Codex2gpt 登录</title>
                <style>
                  :root {
                    color-scheme: dark;
                    --bg-0: #0b1020;
                    --bg-1: #151c33;
                    --text-0: #eaf0ff;
                    --text-1: #a8b3d9;
                    --accent: #66a3ff;
                    --accent-strong: #3f89ff;
                    --border: #2d3759;
                    --danger: #ff6b81;
                  }
                  * { box-sizing: border-box; }
                  body {
                    margin: 0;
                    min-height: 100vh;
                    display: grid;
                    place-items: center;
                    padding: 24px;
                    font-family: Inter, "PingFang SC", "Microsoft YaHei", -apple-system, sans-serif;
                    color: var(--text-0);
                    background:
                      radial-gradient(circle at 20% 20%, #1f2d52 0%, transparent 45%),
                      radial-gradient(circle at 80% 10%, #1d2a47 0%, transparent 38%),
                      linear-gradient(160deg, var(--bg-0), #070b18 55%, #0b1327);
                  }
                  .card {
                    width: 100%;
                    max-width: 420px;
                    border: 1px solid var(--border);
                    border-radius: 16px;
                    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45);
                    overflow: hidden;
                  }
                  .card-head {
                    padding: 22px 24px 16px 24px;
                    border-bottom: 1px solid rgba(255,255,255,0.06);
                    background: linear-gradient(180deg, rgba(102,163,255,0.12), rgba(102,163,255,0.02));
                  }
                  .brand {
                    font-size: 12px;
                    letter-spacing: 0.12em;
                    color: var(--text-1);
                    text-transform: uppercase;
                    margin-bottom: 10px;
                  }
                  h1 {
                    margin: 0 0 6px 0;
                    font-size: 22px;
                    line-height: 1.25;
                  }
                  .subtitle {
                    margin: 0;
                    color: var(--text-1);
                    font-size: 13px;
                    line-height: 1.55;
                  }
                  form {
                    display: grid;
                    gap: 14px;
                    padding: 20px 24px 24px 24px;
                  }
                  label {
                    font-size: 12px;
                    color: var(--text-1);
                    letter-spacing: 0.02em;
                  }
                  input[type="password"] {
                    width: 100%;
                    margin-top: 8px;
                    background: var(--bg-1);
                    color: var(--text-0);
                    border: 1px solid var(--border);
                    border-radius: 10px;
                    padding: 11px 12px;
                    font-size: 14px;
                    outline: none;
                    transition: border-color .15s ease, box-shadow .15s ease;
                  }
                  input[type="password"]:focus {
                    border-color: var(--accent);
                    box-shadow: 0 0 0 3px rgba(102, 163, 255, 0.18);
                  }
                  button {
                    appearance: none;
                    border: 0;
                    border-radius: 10px;
                    padding: 11px 14px;
                    font-size: 14px;
                    font-weight: 600;
                    color: white;
                    cursor: pointer;
                    background: linear-gradient(180deg, var(--accent), var(--accent-strong));
                    transition: transform .05s ease, filter .2s ease;
                  }
                  button:hover { filter: brightness(1.06); }
                  button:active { transform: translateY(1px); }
                  .hint {
                    margin: 0;
                    font-size: 12px;
                    color: var(--text-1);
                  }
                  .error {
                    display: none;
                    margin: 0;
                    color: var(--danger);
                    font-size: 12px;
                  }
                  .error.show { display: block; }
                </style>
              </head>
              <body>
                <section class="card">
                  <header class="card-head">
                    <div class="brand">Codex2gpt Dashboard</div>
                    <h1>登录控制台</h1>
                    <p class="subtitle">请输入管理密码后继续。登录成功将创建会话并自动跳转。</p>
                  </header>
                  <form id="login-form">
                    <label>
                      管理密码
                      <input type="password" name="password" placeholder="请输入 Dashboard 密码" autocomplete="current-password" required />
                    </label>
                    <button type="submit">登录</button>
                    <p class="hint">密码来自环境变量 <code>LITE_DASHBOARD_PASSWORD</code>。</p>
                    <p id="error" class="error">登录失败，请检查密码后重试。</p>
                  </form>
                </section>
                <script>
                  const form = document.getElementById("login-form");
                  const error = document.getElementById("error");
                  form.addEventListener("submit", async (event) => {
                    event.preventDefault();
                    error.classList.remove("show");
                    const formData = new FormData(form);
                    const payload = { password: String(formData.get("password") || "") };
                    const response = await fetch("/auth/login", {
                      method: "POST",
                      headers: { "Content-Type": "application/json" },
                      credentials: "same-origin",
                      body: JSON.stringify(payload),
                    });
                    if (response.ok) {
                      window.location.href = "/";
                      return;
                    }
                    error.classList.add("show");
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
    _sync_legacy_runtime_state(session_id=session_id, remote_addr=_client_ip(request), force=True)
    response = JSONResponse(status_code=200, content={"ok": True})
    _set_dashboard_cookie(response, session_id)
    return response


@app.delete("/auth/login")
def auth_logout(request: Request):
    session_id = request.cookies.get(DASHBOARD_SESSION_COOKIE, "").strip()
    if session_id:
        STATE_DB.delete_dashboard_session(session_id)
        try:
            legacy.STATE_DB.delete_dashboard_session(session_id)
        except Exception:
            pass
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
    _sync_legacy_runtime_state(
        session_id=request.cookies.get(DASHBOARD_SESSION_COOKIE, "").strip(),
        remote_addr=_client_ip(request),
    )
    full_path = "/auth/accounts"
    query = request.url.query
    if query:
        full_path = f"{full_path}?{query}"
    bridge = _LegacyBridgeHandler("GET", full_path, dict(request.headers), b"", _client_ip(request))
    bridge.do_GET()
    passthrough_headers: dict[str, str] = {}
    for key, value in bridge.response_headers:
        low = key.lower()
        if low in {"content-length", "connection", "transfer-encoding"}:
            continue
        passthrough_headers.setdefault(key, value)
    return Response(content=bridge.response_body, status_code=bridge.response_status, headers=passthrough_headers)


@app.get("/auth/accounts/export")
def auth_accounts_export(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    _sync_legacy_runtime_state(
        session_id=request.cookies.get(DASHBOARD_SESSION_COOKIE, "").strip(),
        remote_addr=_client_ip(request),
    )
    bridge = _LegacyBridgeHandler("GET", "/auth/accounts/export", dict(request.headers), b"", _client_ip(request))
    bridge.do_GET()
    passthrough_headers: dict[str, str] = {}
    for key, value in bridge.response_headers:
        low = key.lower()
        if low in {"content-length", "connection", "transfer-encoding"}:
            continue
        passthrough_headers.setdefault(key, value)
    return Response(content=bridge.response_body, status_code=bridge.response_status, headers=passthrough_headers)


@app.post("/auth/accounts/import")
async def auth_accounts_import(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    body = await request.body()
    _sync_legacy_runtime_state(
        session_id=request.cookies.get(DASHBOARD_SESSION_COOKIE, "").strip(),
        remote_addr=_client_ip(request),
    )
    bridge = _LegacyBridgeHandler("POST", "/auth/accounts/import", dict(request.headers), body, _client_ip(request))
    bridge.do_POST()
    passthrough_headers: dict[str, str] = {}
    for key, value in bridge.response_headers:
        low = key.lower()
        if low in {"content-length", "connection", "transfer-encoding"}:
            continue
        passthrough_headers.setdefault(key, value)
    return Response(content=bridge.response_body, status_code=bridge.response_status, headers=passthrough_headers)


@app.post("/auth/accounts/batch-delete")
async def auth_accounts_batch_delete(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    body = await request.body()
    _sync_legacy_runtime_state(
        session_id=request.cookies.get(DASHBOARD_SESSION_COOKIE, "").strip(),
        remote_addr=_client_ip(request),
    )
    bridge = _LegacyBridgeHandler("POST", "/auth/accounts/batch-delete", dict(request.headers), body, _client_ip(request))
    bridge.do_POST()
    passthrough_headers: dict[str, str] = {}
    for key, value in bridge.response_headers:
        low = key.lower()
        if low in {"content-length", "connection", "transfer-encoding"}:
            continue
        passthrough_headers.setdefault(key, value)
    return Response(content=bridge.response_body, status_code=bridge.response_status, headers=passthrough_headers)


@app.post("/auth/accounts/batch-status")
async def auth_accounts_batch_status(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    body = await request.body()
    _sync_legacy_runtime_state(
        session_id=request.cookies.get(DASHBOARD_SESSION_COOKIE, "").strip(),
        remote_addr=_client_ip(request),
    )
    bridge = _LegacyBridgeHandler("POST", "/auth/accounts/batch-status", dict(request.headers), body, _client_ip(request))
    bridge.do_POST()
    passthrough_headers: dict[str, str] = {}
    for key, value in bridge.response_headers:
        low = key.lower()
        if low in {"content-length", "connection", "transfer-encoding"}:
            continue
        passthrough_headers.setdefault(key, value)
    return Response(content=bridge.response_body, status_code=bridge.response_status, headers=passthrough_headers)


@app.post("/auth/login-start")
async def auth_login_start(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    _ = await request.body()
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("utf-8")).digest()).decode("ascii").rstrip("=")
    state = secrets.token_urlsafe(24)
    redirect_uri = oauth_redirect_uri_for_request(request)
    STATE_DB.upsert_oauth_pkce_session(
        state,
        verifier=verifier,
        redirect_uri=redirect_uri,
        created_at=now_iso(),
        completed=False,
    )
    authorize_url = (
        AUTHORIZE_URL + "?"
        + urllib.parse.urlencode(
            {
                "response_type": "code",
                "client_id": CLIENT_ID,
                "redirect_uri": redirect_uri,
                "scope": "openid profile email offline_access",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "originator": "codex_cli_rs",
                "codex_cli_simplified_flow": "true",
                "state": state,
            }
        )
    )
    return {
        "state": state,
        "authorize_url": authorize_url,
        "redirect_uri": redirect_uri,
        "callback_server": {"ok": True, "mode": "cloud", "redirect_uri": redirect_uri, "error": ""},
    }


def _complete_oauth_callback(code: str, state: str) -> dict[str, Any]:
    code = str(code or "").strip()
    state = str(state or "").strip()
    if not code or not state:
        raise ValueError("Missing code or state parameter")
    pending = STATE_DB.get_oauth_pkce_session(state)
    if not pending:
        raise ValueError("Invalid or expired OAuth session. Please try again.")
    if oauth_session_expired(str(pending.get("created_at") or "")):
        STATE_DB.delete_oauth_pkce_session(state)
        raise ValueError("Invalid or expired OAuth session. Please try again.")
    if bool(pending.get("completed")):
        return {"completed_state": state, "already_completed": True}
    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "redirect_uri": str(pending.get("redirect_uri") or ""),
            "code_verifier": str(pending.get("verifier") or ""),
        }
    ).encode("utf-8")
    token_req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(token_req, timeout=30) as response:
        tokens = json.load(response)
    id_claims = decode_jwt_payload(str(tokens.get("id_token") or ""))
    auth_claims = id_claims.get("https://api.openai.com/auth") if isinstance(id_claims.get("https://api.openai.com/auth"), dict) else {}
    profile = id_claims.get("https://api.openai.com/profile") if isinstance(id_claims.get("https://api.openai.com/profile"), dict) else {}
    email = str(id_claims.get("email") or profile.get("email") or "").strip()
    sub = str(id_claims.get("sub") or "").strip()
    filename_root = email or sub or f"oauth_{int(time.time())}"
    safe_root = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in filename_root).strip("._-") or f"oauth_{int(time.time())}"
    entry_id = f"{safe_root}.json"
    account_id = str(tokens.get("account_id") or auth_claims.get("chatgpt_account_id") or "").strip()
    plan_type = str(auth_claims.get("chatgpt_plan_type") or "").strip()
    payload = {
        "auth_mode": "chatgpt",
        "email": email,
        "user_id": sub,
        "plan_type": plan_type,
        "last_refresh": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "tokens": {
            "access_token": tokens.get("access_token"),
            "refresh_token": tokens.get("refresh_token"),
            "id_token": tokens.get("id_token"),
            "token_type": tokens.get("token_type"),
            "expires_in": tokens.get("expires_in"),
            "account_id": account_id,
        },
    }
    STATE_DB.upsert_account(
        entry_id,
        auth_file=f"db://accounts/{entry_id}",
        email=email,
        user_id=sub,
        account_id=account_id,
        plan_type=plan_type,
        status="active",
        refresh_token=str(tokens.get("refresh_token") or ""),
        proxy_id=None,
        last_error=None,
        metadata={"source": "oauth_cloud", "id_claims": id_claims},
        quota={},
        usage={"input_tokens": 0, "output_tokens": 0, "request_count": 0},
        auth_payload=payload,
    )
    STATE_DB.mark_oauth_pkce_completed(state)
    return {"filename": entry_id, "account_payload": payload, "completed_state": state, "already_completed": False}


@app.get("/auth/callback")
def auth_callback(request: Request, code: str = "", state: str = "", error: str = "", error_description: str = ""):
    if error:
        return HTMLResponse(oauth_callback_result_html(False, "Login Failed", error_description or error), status_code=400)
    try:
        result = _complete_oauth_callback(code, state)
    except Exception as exc:
        return HTMLResponse(oauth_callback_result_html(False, "Login Failed", str(exc)), status_code=400)
    if result.get("already_completed"):
        html = oauth_callback_result_html(True, "OAuth login complete", "This login session was already completed.")
    else:
        email = ((result.get("account_payload") or {}).get("email") or "unknown").strip() or "unknown"
        html = oauth_callback_result_html(True, "OAuth login complete", f"Saved account {result['filename']} ({email}).")
    return HTMLResponse(html, status_code=200)


@app.post("/auth/code-relay")
async def auth_code_relay(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    payload = await request.json()
    callback_url = str((payload.get("callback_url") or payload.get("callbackUrl") or "") if isinstance(payload, dict) else "").strip()
    if not callback_url:
        return JSONResponse(status_code=400, content={"error": {"type": "invalid_request_error", "message": "callbackUrl is required"}})
    try:
        url = urllib.parse.urlsplit(callback_url)
    except Exception:
        return JSONResponse(status_code=400, content={"error": {"type": "invalid_request_error", "message": "invalid callbackUrl"}})
    params = urllib.parse.parse_qs(url.query)
    error = (params.get("error") or [""])[0]
    error_description = (params.get("error_description") or [""])[0]
    if error:
        return JSONResponse(status_code=400, content={"error": {"type": "authentication_error", "message": error_description or error}})
    code = (params.get("code") or [""])[0]
    state = (params.get("state") or [""])[0]
    try:
        result = _complete_oauth_callback(code, state)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"error": {"type": "authentication_error", "message": str(exc)}})
    return {
        "ok": True,
        "already_completed": bool(result.get("already_completed")),
        "filename": result.get("filename"),
        "email": ((result.get("account_payload") or {}).get("email") or ""),
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
        result = _persist_auth_payload(payload, source="local_import", entry_id_override=os.path.basename(path))
        imported.append(result["entry_id"])
    return {"imported": imported, "count": len(imported), "auth_dir": auth_dir}


@app.post("/admin/connector/session/create")
async def connector_create_session(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    payload = await request.json() if request.method == "POST" else {}
    ttl = int((payload or {}).get("ttl_seconds") or CONNECTOR_SESSION_TTL_SECONDS) if isinstance(payload, dict) else CONNECTOR_SESSION_TTL_SECONDS
    ttl = max(60, min(ttl, 1800))
    session_id = secrets.token_hex(8)
    token = f"c2gcs_{secrets.token_urlsafe(30)}"
    STATE_DB.create_connector_session(
        session_id,
        token_hash=hash_api_key(token),
        expires_at=_iso_after_seconds(ttl),
        remote_addr=_client_ip(request),
    )
    public_base = (os.environ.get("LITE_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not public_base:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        proto = request.headers.get("x-forwarded-proto") or "https"
        public_base = f"{proto}://{host}".rstrip("/")
    install_url = (
        f"{public_base}/connector/install.sh?token={urllib.parse.quote(token, safe='')}"
        f"&session_id={urllib.parse.quote(session_id, safe='')}"
    )
    return {"ok": True, "session_id": session_id, "expires_in_seconds": ttl, "install_url": install_url, "token": token}


@app.get("/admin/connector/session/{session_id}")
def connector_session_status(session_id: str, request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    session = STATE_DB.get_connector_session(session_id)
    if not session:
        return JSONResponse(status_code=404, content={"error": {"type": "not_found", "message": "connector session not found"}})
    expires_at = _parse_iso(str(session.get("expires_at") or ""))
    is_expired = bool(expires_at and expires_at <= datetime.datetime.now(datetime.timezone.utc))
    if is_expired and str(session.get("status") or "pending") == "pending":
        STATE_DB.update_connector_session(session_id, status="expired")
        session = STATE_DB.get_connector_session(session_id) or session
    status = str(session.get("status") or "pending")
    message = ""
    if status == "duplicate":
        message = "账号已存在，已更新该账号认证信息。"
    elif status == "completed":
        message = "账号上传成功。"
    elif status == "failed":
        message = "上传失败，请重新生成命令后重试。"
    elif status == "expired":
        message = "会话已过期，请重新生成命令。"
    return {
        "session_id": session_id,
        "status": status,
        "expires_at": session.get("expires_at") or "",
        "uploaded_entry_id": session.get("uploaded_entry_id") or "",
        "uploaded_email": session.get("uploaded_email") or "",
        "error": session.get("error_text") or "",
        "message": message,
    }


@app.get("/connector/install.sh")
def connector_install_script(request: Request, token: str = "", session_id: str = ""):
    raw_token = str(token or "").strip()
    raw_session_id = str(session_id or "").strip()
    if not raw_token:
        return Response("missing token\n", status_code=400, media_type="text/plain; charset=utf-8")
    if not raw_session_id:
        return Response("missing session_id\n", status_code=400, media_type="text/plain; charset=utf-8")
    public_base = (os.environ.get("LITE_PUBLIC_BASE_URL") or "").strip().rstrip("/")
    if not public_base:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
        proto = request.headers.get("x-forwarded-proto") or "https"
        public_base = f"{proto}://{host}".rstrip("/")
    script = f"""#!/usr/bin/env bash
set -euo pipefail

BASE_URL="{public_base}"
TOKEN="{raw_token}"
SESSION_ID="{raw_session_id}"
AUTH_PATH="${{AUTH_PATH:-$HOME/.codex/auth.json}}"

if [ ! -f "$AUTH_PATH" ]; then
  echo "auth file not found: $AUTH_PATH" >&2
  exit 1
fi

PAYLOAD="$(python3 - "$TOKEN" "$SESSION_ID" "$AUTH_PATH" <<'PY'
import json
import sys

token = sys.argv[1]
session_id = sys.argv[2]
auth_path = sys.argv[3]
with open(auth_path, "r", encoding="utf-8") as f:
    auth_payload = json.load(f)
print(json.dumps({{"token": token, "session_id": session_id, "auth_payload": auth_payload}}, separators=(",", ":")))
PY
)"

echo "Uploading auth from $AUTH_PATH ..."
curl -fsS "$BASE_URL/admin/connector/upload-auth" \\
  -H 'content-type: application/json' \\
  --data-binary "$PAYLOAD"
"""
    return Response(script, media_type="text/x-shellscript; charset=utf-8")


@app.post("/admin/connector/upload-auth")
async def connector_upload_auth(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": {"type": "invalid_request_error", "message": "request body must be valid json"}})
    token = str((body.get("token") if isinstance(body, dict) else "") or "").strip()
    auth_payload = body.get("auth_payload") if isinstance(body, dict) else None
    if not token:
        return JSONResponse(status_code=400, content={"error": {"type": "invalid_request_error", "message": "token is required"}})
    if not isinstance(auth_payload, dict):
        return JSONResponse(status_code=400, content={"error": {"type": "invalid_request_error", "message": "auth_payload must be object"}})
    if len(json.dumps(auth_payload, ensure_ascii=False)) > 1024 * 512:
        return JSONResponse(status_code=400, content={"error": {"type": "invalid_request_error", "message": "auth_payload too large"}})

    token_hash = hash_api_key(token)
    matched: dict[str, Any] | None = None
    matched_id = ""
    session_id = str((body.get("session_id") if isinstance(body, dict) else "") or "").strip()
    if session_id:
        item = STATE_DB.get_connector_session(session_id)
        if item and str(item.get("token_hash") or "") == token_hash:
            matched = item
            matched_id = session_id
    if not matched:
        return JSONResponse(status_code=400, content={"error": {"type": "invalid_request_error", "message": "invalid or expired token"}})
    expires_at = _parse_iso(str(matched.get("expires_at") or ""))
    if not expires_at or expires_at <= datetime.datetime.now(datetime.timezone.utc):
        STATE_DB.update_connector_session(matched_id, status="expired")
        return JSONResponse(status_code=400, content={"error": {"type": "invalid_request_error", "message": "token expired"}})
    if str(matched.get("status") or "pending") != "pending":
        return JSONResponse(status_code=400, content={"error": {"type": "invalid_request_error", "message": "token already used"}})
    try:
        existing_entry = _find_existing_account_entry(auth_payload)
        is_duplicate = bool(existing_entry)
        result = _persist_auth_payload(
            auth_payload,
            source="connector_upload",
            entry_id_override=existing_entry,
        )
        STATE_DB.update_connector_session(
            matched_id,
            status="duplicate" if is_duplicate else "completed",
            uploaded_entry_id=result["entry_id"],
            uploaded_email=result["email"],
            error_text="",
        )
    except Exception as exc:
        STATE_DB.update_connector_session(matched_id, status="failed", error_text=str(exc))
        return JSONResponse(status_code=400, content={"error": {"type": "invalid_request_error", "message": str(exc)}})
    _sync_legacy_runtime_state(force=True)
    return {"ok": True, "entry_id": result["entry_id"], "email": result["email"], "duplicate": bool(existing_entry)}


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


@app.get("/admin/storage-diagnostics")
def storage_diagnostics(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    diagnostics = STATE_DB.storage_diagnostics()
    diagnostics.update(
        {
            "legacy_state_shared": legacy.STATE_DB is STATE_DB
            or legacy.STATE_DB is getattr(STATE_DB, "_sqlite", None),
            "legacy_state_type": type(legacy.STATE_DB).__name__,
            "serverless_state_type": type(STATE_DB).__name__,
            "legacy_sync_error": _LEGACY_LAST_SYNC_ERROR,
            "env_api_key_configured": bool(API_KEY),
            "legacy_env_api_key_configured": bool(getattr(legacy, "API_KEY", "")),
            "env_synthetic_key_present": bool(STATE_DB.get_api_key(getattr(legacy, "ENV_LITE_API_KEY_KEY_ID", "env_lite_api_key"))),
        }
    )
    return diagnostics


@app.post("/admin/runtime-jobs/run")
async def run_runtime_job(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    payload = await request.json()
    job = str((payload.get("job") if isinstance(payload, dict) else "") or "").strip()
    _sync_legacy_runtime_state(
        session_id=request.cookies.get(DASHBOARD_SESSION_COOKIE, "").strip(),
        remote_addr=_client_ip(request),
        force=True,
    )
    if job == "quota_refresh":
        result = legacy.refresh_all_account_quotas()
        result["storage"] = STATE_DB.storage_diagnostics()
        return result
    if job == "token_refresh":
        return {"refreshed": legacy.refresh_accounts_if_needed(force=False, refresh_expired=True)}
    if job == "proxy_health":
        return {"data": [legacy.proxy_health_check(proxy) for proxy in STATE_DB.list_proxies()]}
    if job == "fingerprint_refresh":
        return legacy.refresh_fingerprint_cache(force=True)
    return JSONResponse(
        status_code=400,
        content={"error": {"type": "invalid_request_error", "message": "unknown runtime job"}},
    )


@app.post("/admin/quota-refresh")
def run_quota_refresh(request: Request):
    reject = _require_dashboard(request)
    if reject is not None:
        return reject
    _sync_legacy_runtime_state(
        session_id=request.cookies.get(DASHBOARD_SESSION_COOKIE, "").strip(),
        remote_addr=_client_ip(request),
        force=True,
    )
    result = legacy.refresh_all_account_quotas()
    result["storage"] = STATE_DB.storage_diagnostics()
    return result


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
    _sync_legacy_runtime_state(force=True)
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
    _sync_legacy_runtime_state(force=True)
    return {"deleted": True, "key_id": key_id}

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def legacy_fallback(path: str, request: Request):
    # Explicit routes above take precedence; this is only for unmigrated endpoints.
    full_path = "/" + path
    query = request.url.query
    if query:
        full_path = f"{full_path}?{query}"
    _sync_legacy_runtime_state(
        session_id=request.cookies.get(DASHBOARD_SESSION_COOKIE, "").strip(),
        remote_addr=_client_ip(request),
    )
    body = await request.body()
    wants_stream = _is_streaming_request("/" + path, request.method, body)
    stream_sink = _StreamSink() if wants_stream else None
    bridge = _LegacyBridgeHandler(
        request.method,
        full_path,
        dict(request.headers),
        body,
        _client_ip(request),
        wfile=stream_sink,
    )
    method = request.method.upper()
    failure_holder: dict[str, Exception] = {}

    def _run():
        try:
            if method == "GET":
                bridge.do_GET()
            elif method == "POST":
                bridge.do_POST()
            elif method == "DELETE":
                bridge.do_DELETE()
        except Exception as exc:  # pragma: no cover
            failure_holder["error"] = exc
        finally:
            if stream_sink is not None:
                stream_sink.close()

    if wants_stream:
        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        bridge.headers_ready.wait(timeout=5)
        if failure_holder.get("error") is not None:
            raise failure_holder["error"]
        passthrough_headers: dict[str, str] = {}
        for key, value in bridge.response_headers:
            low = key.lower()
            if low in {"content-length", "connection", "transfer-encoding"}:
                continue
            passthrough_headers.setdefault(key, value)
        return StreamingResponse(
            stream_sink.iter_bytes(),
            status_code=bridge.response_status,
            headers=passthrough_headers,
        )

    if method == "GET":
        bridge.do_GET()
    elif method == "POST":
        bridge.do_POST()
    elif method == "DELETE":
        bridge.do_DELETE()
    elif method in {"PUT", "PATCH", "OPTIONS"}:
        return JSONResponse(
            status_code=405,
            content={"error": {"type": "method_not_allowed", "message": f"{method} is not supported by legacy bridge"}},
        )
    else:
        return JSONResponse(
            status_code=405,
            content={"error": {"type": "method_not_allowed", "message": f"{method} is not supported"}},
        )
    passthrough_headers: dict[str, str] = {}
    for key, value in bridge.response_headers:
        low = key.lower()
        if low in {"content-length", "connection", "transfer-encoding"}:
            continue
        # Keep first value for duplicates; sufficient for current usage.
        passthrough_headers.setdefault(key, value)
    return Response(content=bridge.response_body, status_code=bridge.response_status, headers=passthrough_headers)

