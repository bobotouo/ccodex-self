"""State adapter for serverless runtime.

Uses Postgres when DATABASE_URL/POSTGRES_URL is configured, otherwise falls back
to local sqlite RuntimeStateStore.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from codex2gpt import state_db as _state_db
from codex2gpt.state_db import RuntimeStateStore


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, separators=(",", ":"))


class ServerlessStateStore:
    def __init__(self):
        self.database_url = (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or "").strip()
        if self.database_url:
            try:
                import psycopg  # type: ignore
            except Exception as exc:  # pragma: no cover
                raise RuntimeError("psycopg is required when DATABASE_URL is configured") from exc
            self._psycopg = psycopg
            self._backend = "postgres"
            self._init_pg_schema()
            self._sqlite = None
            # 全量 state_db 能力（usage_events、proxies 等）仍由本地 sqlite 承载，与 Vercel Postgres 中的
            # accounts/api_keys 并存；legacy 桥与显式 /admin 必须共享同一状态对象，见 serverless_app 绑定。
            runtime_root = os.path.abspath(os.environ.get("LITE_RUNTIME_ROOT", "/tmp/codex2gpt-runtime"))
            os.makedirs(runtime_root, exist_ok=True)
            aux_path = os.path.abspath(
                os.environ.get("LITE_AUX_STATE_DB", os.path.join(runtime_root, "aux_state.sqlite3"))
            )
            self._aux = RuntimeStateStore(aux_path)
        else:
            runtime_root = os.path.abspath(os.environ.get("LITE_RUNTIME_ROOT", "/tmp/codex2gpt-runtime"))
            state_db_path = os.path.abspath(os.environ.get("LITE_STATE_DB", os.path.join(runtime_root, "state.sqlite3")))
            self._sqlite = RuntimeStateStore(state_db_path)
            self._backend = "sqlite"
            self._psycopg = None
            self._aux = None

    @property
    def backend(self) -> str:
        return self._backend

    def _pg_conn(self):
        return self._psycopg.connect(self.database_url, autocommit=True)

    def storage_diagnostics(self) -> dict[str, Any]:
        parsed = urlparse(self.database_url) if self.database_url else None
        payload: dict[str, Any] = {
            "backend": self._backend,
            "database_url_configured": bool(self.database_url),
            "database_host": parsed.hostname if parsed else "",
            "database_provider_hint": "neon" if parsed and "neon.tech" in str(parsed.hostname or "") else "",
            "aux_sqlite_enabled": bool(self._aux is not None),
        }
        if self._backend == "sqlite":
            api_summary = self._sqlite.get_api_key_usage_summary(hours=None)
            accounts = self._sqlite.list_accounts()
            payload.update(
                {
                    "api_key_count": api_summary.get("key_count", 0),
                    "api_key_usage_request_count": api_summary.get("total_request_count", 0),
                    "account_count": len(accounts),
                    "accounts_with_quota": sum(1 for item in accounts if item.get("quota")),
                    "accounts_with_usage": sum(1 for item in accounts if item.get("usage")),
                }
            )
            return payload
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM accounts")
                account_count = int((cur.fetchone() or [0])[0] or 0)
                cur.execute("SELECT COUNT(*) FROM accounts WHERE quota_json IS NOT NULL AND quota_json <> '{}' AND quota_json <> ''")
                accounts_with_quota = int((cur.fetchone() or [0])[0] or 0)
                cur.execute("SELECT COUNT(*) FROM accounts WHERE usage_json IS NOT NULL AND usage_json <> '{}' AND usage_json <> ''")
                accounts_with_usage = int((cur.fetchone() or [0])[0] or 0)
                cur.execute("SELECT COUNT(*) FROM api_keys")
                api_key_count = int((cur.fetchone() or [0])[0] or 0)
                cur.execute("SELECT COUNT(*), COALESCE(SUM(request_count), 0), MAX(recorded_at) FROM api_key_usage_events")
                usage_row = cur.fetchone() or [0, 0, None]
                cur.execute(
                    """
                    SELECT key_id, name, key_prefix, enabled, last_used_at
                    FROM api_keys
                    ORDER BY created_at DESC, key_id DESC
                    LIMIT 10
                    """
                )
                key_rows = cur.fetchall()
        payload.update(
            {
                "account_count": account_count,
                "accounts_with_quota": accounts_with_quota,
                "accounts_with_usage": accounts_with_usage,
                "api_key_count": api_key_count,
                "api_key_usage_event_count": int(usage_row[0] or 0),
                "api_key_usage_request_count": int(usage_row[1] or 0),
                "last_api_key_usage_at": usage_row[2],
                "recent_api_keys": [
                    {
                        "key_id": row[0],
                        "name": row[1],
                        "key_prefix": row[2],
                        "enabled": bool(row[3]),
                        "last_used_at": row[4],
                    }
                    for row in key_rows
                ],
            }
        )
        return payload

    def _init_pg_schema(self) -> None:
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS accounts (
                        entry_id TEXT PRIMARY KEY,
                        auth_file TEXT,
                        email TEXT,
                        user_id TEXT,
                        account_id TEXT,
                        plan_type TEXT,
                        status TEXT NOT NULL DEFAULT 'active',
                        refresh_token TEXT,
                        proxy_id TEXT,
                        last_error TEXT,
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        quota_json TEXT NOT NULL DEFAULT '{}',
                        usage_json TEXT NOT NULL DEFAULT '{}',
                        auth_payload_json TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                    );
                    CREATE TABLE IF NOT EXISTS dashboard_sessions (
                        session_id TEXT PRIMARY KEY,
                        remote_addr TEXT,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_dashboard_sessions_expires_at
                    ON dashboard_sessions(expires_at);
                    CREATE TABLE IF NOT EXISTS api_keys (
                        key_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        api_key TEXT NOT NULL DEFAULT '',
                        key_hash TEXT NOT NULL UNIQUE,
                        key_prefix TEXT NOT NULL,
                        enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        last_used_at TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_api_keys_enabled
                    ON api_keys(enabled);
                    CREATE TABLE IF NOT EXISTS api_key_usage_events (
                        event_id BIGSERIAL PRIMARY KEY,
                        key_id TEXT NOT NULL REFERENCES api_keys(key_id) ON DELETE CASCADE,
                        recorded_at TEXT NOT NULL,
                        input_tokens INTEGER NOT NULL DEFAULT 0,
                        output_tokens INTEGER NOT NULL DEFAULT 0,
                        request_count INTEGER NOT NULL DEFAULT 1,
                        success_count INTEGER NOT NULL DEFAULT 1,
                        failure_count INTEGER NOT NULL DEFAULT 0,
                        metadata_json TEXT NOT NULL DEFAULT '{}'
                    );
                    CREATE INDEX IF NOT EXISTS idx_api_key_usage_events_key_time
                    ON api_key_usage_events(key_id, recorded_at);
                    CREATE TABLE IF NOT EXISTS oauth_pkce_sessions (
                        state TEXT PRIMARY KEY,
                        verifier TEXT NOT NULL,
                        redirect_uri TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        completed INTEGER NOT NULL DEFAULT 0
                    );
                    CREATE INDEX IF NOT EXISTS idx_oauth_pkce_sessions_created_at
                    ON oauth_pkce_sessions(created_at);
                    CREATE TABLE IF NOT EXISTS connector_sessions (
                        session_id TEXT PRIMARY KEY,
                        token_hash TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        expires_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        remote_addr TEXT,
                        uploaded_entry_id TEXT,
                        uploaded_email TEXT,
                        error_text TEXT,
                        last_seen_at TEXT NOT NULL
                    );
                    CREATE INDEX IF NOT EXISTS idx_connector_sessions_expires_at
                    ON connector_sessions(expires_at);
                    """
                )
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS auth_file TEXT")
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS email TEXT")
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS user_id TEXT")
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS account_id TEXT")
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS plan_type TEXT")
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'active'")
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS refresh_token TEXT")
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS proxy_id TEXT")
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS last_error TEXT")
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS metadata_json TEXT NOT NULL DEFAULT '{}'")
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS quota_json TEXT NOT NULL DEFAULT '{}'")
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS usage_json TEXT NOT NULL DEFAULT '{}'")
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS auth_payload_json TEXT NOT NULL DEFAULT '{}'")
                cur.execute("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")

    # ---- dashboard sessions ----
    def create_dashboard_session(self, session_id: str, *, expires_at: str, remote_addr: str | None = None, created_at: str | None = None) -> None:
        if self._backend == "sqlite":
            self._sqlite.create_dashboard_session(session_id, expires_at=expires_at, remote_addr=remote_addr, created_at=created_at)
            return
        created = created_at or _utcnow_iso()
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dashboard_sessions (session_id, remote_addr, created_at, expires_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT(session_id) DO UPDATE SET
                        remote_addr = EXCLUDED.remote_addr,
                        created_at = EXCLUDED.created_at,
                        expires_at = EXCLUDED.expires_at
                    """,
                    (session_id, remote_addr, created, expires_at),
                )

    def validate_dashboard_session(self, session_id: str, now_ts: str | None = None) -> bool:
        if self._backend == "sqlite":
            return self._sqlite.validate_dashboard_session(session_id, now_ts=now_ts)
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT expires_at FROM dashboard_sessions WHERE session_id = %s", (session_id,))
                row = cur.fetchone()
        if not row:
            return False
        now = datetime.fromisoformat(now_ts) if now_ts else datetime.now(timezone.utc)
        expires = datetime.fromisoformat(str(row[0]))
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return expires > now

    def delete_dashboard_session(self, session_id: str) -> None:
        if self._backend == "sqlite":
            self._sqlite.delete_dashboard_session(session_id)
            return
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM dashboard_sessions WHERE session_id = %s", (session_id,))

    def cleanup_expired_dashboard_sessions(self, now_ts: str | None = None) -> int:
        if self._backend == "sqlite":
            return self._sqlite.cleanup_expired_dashboard_sessions(now_ts=now_ts)
        cutoff = now_ts or _utcnow_iso()
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM dashboard_sessions WHERE expires_at <= %s", (cutoff,))
                return int(cur.rowcount or 0)

    # ---- counts/status ----
    def list_accounts(self) -> list[dict[str, Any]]:
        if self._backend == "sqlite":
            return self._sqlite.list_accounts()
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        entry_id, auth_file, email, user_id, account_id, plan_type, status,
                        refresh_token, proxy_id, last_error, metadata_json, quota_json, usage_json,
                        auth_payload_json, created_at, updated_at
                    FROM accounts
                    ORDER BY entry_id ASC
                    """
                )
                rows = cur.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            result.append(
                {
                    "entry_id": row[0],
                    "auth_file": row[1],
                    "email": row[2],
                    "user_id": row[3],
                    "account_id": row[4],
                    "plan_type": row[5],
                    "status": row[6],
                    "refresh_token": row[7],
                    "proxy_id": row[8],
                    "last_error": row[9],
                    "metadata": json.loads(row[10] or "{}"),
                    "quota": json.loads(row[11] or "{}"),
                    "usage": json.loads(row[12] or "{}"),
                    "auth_payload": json.loads(row[13] or "{}"),
                    "created_at": row[14],
                    "updated_at": row[15],
                }
            )
        return result

    def get_account(self, entry_id: str) -> dict[str, Any] | None:
        if self._backend == "sqlite":
            return self._sqlite.get_account(entry_id)
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        entry_id, auth_file, email, user_id, account_id, plan_type, status,
                        refresh_token, proxy_id, last_error, metadata_json, quota_json, usage_json,
                        auth_payload_json, created_at, updated_at
                    FROM accounts WHERE entry_id = %s
                    """,
                    (entry_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "entry_id": row[0],
            "auth_file": row[1],
            "email": row[2],
            "user_id": row[3],
            "account_id": row[4],
            "plan_type": row[5],
            "status": row[6],
            "refresh_token": row[7],
            "proxy_id": row[8],
            "last_error": row[9],
            "metadata": json.loads(row[10] or "{}"),
            "quota": json.loads(row[11] or "{}"),
            "usage": json.loads(row[12] or "{}"),
            "auth_payload": json.loads(row[13] or "{}"),
            "created_at": row[14],
            "updated_at": row[15],
        }

    def upsert_account(self, entry_id: str, **fields: Any) -> dict[str, Any]:
        if self._backend == "sqlite":
            return self._sqlite.upsert_account(entry_id, **fields)
        existing = self.get_account(entry_id) or {}
        now = _utcnow_iso()
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                created_at = existing.get("created_at") or now
                cur.execute(
                    """
                    INSERT INTO accounts (
                        entry_id, auth_file, email, user_id, account_id, plan_type, status,
                        refresh_token, proxy_id, last_error, metadata_json, quota_json, usage_json,
                        auth_payload_json, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(entry_id) DO UPDATE SET
                        auth_file = EXCLUDED.auth_file,
                        email = EXCLUDED.email,
                        user_id = EXCLUDED.user_id,
                        account_id = EXCLUDED.account_id,
                        plan_type = EXCLUDED.plan_type,
                        status = EXCLUDED.status,
                        refresh_token = EXCLUDED.refresh_token,
                        proxy_id = EXCLUDED.proxy_id,
                        last_error = EXCLUDED.last_error,
                        metadata_json = EXCLUDED.metadata_json,
                        quota_json = EXCLUDED.quota_json,
                        usage_json = EXCLUDED.usage_json,
                        auth_payload_json = EXCLUDED.auth_payload_json,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        entry_id,
                        fields.get("auth_file", existing.get("auth_file")),
                        fields.get("email", existing.get("email")),
                        fields.get("user_id", existing.get("user_id")),
                        fields.get("account_id", existing.get("account_id")),
                        fields.get("plan_type", existing.get("plan_type")),
                        fields.get("status", existing.get("status") or "active"),
                        fields.get("refresh_token", existing.get("refresh_token")),
                        fields.get("proxy_id", existing.get("proxy_id")),
                        fields.get("last_error", existing.get("last_error")),
                        _dumps(fields.get("metadata", existing.get("metadata") or {})),
                        _dumps(fields.get("quota", existing.get("quota") or {})),
                        _dumps(fields.get("usage", existing.get("usage") or {})),
                        _dumps(fields.get("auth_payload", existing.get("auth_payload") or {})),
                        created_at,
                        now,
                    ),
                )
        accounts = self.list_accounts()
        return next((item for item in accounts if item["entry_id"] == entry_id), {})

    def list_proxies(self) -> list[dict[str, Any]]:
        if self._backend == "sqlite":
            return self._sqlite.list_proxies()
        if self._aux is not None:
            return self._aux.list_proxies()
        return []

    def list_relay_providers(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        if self._backend == "sqlite":
            return self._sqlite.list_relay_providers(enabled_only=enabled_only)
        if self._aux is not None:
            return self._aux.list_relay_providers(enabled_only=enabled_only)
        return []

    # ---- api keys ----
    def list_api_keys(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        if self._backend == "sqlite":
            return self._sqlite.list_api_keys(enabled_only=enabled_only)
        sql = """
            SELECT key_id, name, api_key, key_hash, key_prefix, enabled, metadata_json, last_used_at, created_at, updated_at
            FROM api_keys
        """
        params: list[Any] = []
        if enabled_only:
            sql += " WHERE enabled = TRUE"
        sql += " ORDER BY created_at DESC, key_id DESC"
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
        result = []
        for row in rows:
            result.append(
                {
                    "key_id": row[0],
                    "name": row[1],
                    "api_key": row[2],
                    "key_hash": row[3],
                    "key_prefix": row[4],
                    "enabled": bool(row[5]),
                    "metadata": json.loads(row[6] or "{}"),
                    "last_used_at": row[7],
                    "created_at": row[8],
                    "updated_at": row[9],
                }
            )
        return result

    def upsert_api_key(
        self,
        key_id: str,
        *,
        name: str,
        api_key: str,
        key_hash: str,
        key_prefix: str,
        enabled: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._backend == "sqlite":
            return self._sqlite.upsert_api_key(
                key_id,
                name=name,
                api_key=api_key,
                key_hash=key_hash,
                key_prefix=key_prefix,
                enabled=enabled,
                metadata=metadata,
            )
        now = _utcnow_iso()
        existing = self.get_api_key(key_id) or {}
        created_at = existing.get("created_at") or now
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO api_keys (
                        key_id, name, api_key, key_hash, key_prefix, enabled, metadata_json, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(key_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        api_key = EXCLUDED.api_key,
                        key_hash = EXCLUDED.key_hash,
                        key_prefix = EXCLUDED.key_prefix,
                        enabled = EXCLUDED.enabled,
                        metadata_json = EXCLUDED.metadata_json,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        key_id,
                        name,
                        api_key,
                        key_hash,
                        key_prefix,
                        enabled,
                        _dumps(metadata if metadata is not None else (existing.get("metadata") or {})),
                        created_at,
                        now,
                    ),
                )
                cur.execute(
                    """
                    SELECT key_id, name, api_key, key_hash, key_prefix, enabled, metadata_json, last_used_at, created_at, updated_at
                    FROM api_keys WHERE key_id = %s
                    """,
                    (key_id,),
                )
                row = cur.fetchone()
        return {
            "key_id": row[0],
            "name": row[1],
            "api_key": row[2],
            "key_hash": row[3],
            "key_prefix": row[4],
            "enabled": bool(row[5]),
            "metadata": json.loads(row[6] or "{}"),
            "last_used_at": row[7],
            "created_at": row[8],
            "updated_at": row[9],
        }

    def delete_api_key(self, key_id: str) -> None:
        if self._backend == "sqlite":
            self._sqlite.delete_api_key(key_id)
            return
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM api_keys WHERE key_id = %s", (key_id,))

    def get_api_key(self, key_id: str) -> dict[str, Any] | None:
        if self._backend == "sqlite":
            return self._sqlite.get_api_key(key_id)
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT key_id, name, api_key, key_hash, key_prefix, enabled, metadata_json, last_used_at, created_at, updated_at
                    FROM api_keys WHERE key_id = %s
                    """,
                    (key_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "key_id": row[0],
            "name": row[1],
            "api_key": row[2],
            "key_hash": row[3],
            "key_prefix": row[4],
            "enabled": bool(row[5]),
            "metadata": json.loads(row[6] or "{}"),
            "last_used_at": row[7],
            "created_at": row[8],
            "updated_at": row[9],
        }

    def get_api_key_by_hash(self, key_hash: str) -> dict[str, Any] | None:
        if self._backend == "sqlite":
            return self._sqlite.get_api_key_by_hash(key_hash)
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT key_id, name, api_key, key_hash, key_prefix, enabled, metadata_json, last_used_at, created_at, updated_at
                    FROM api_keys WHERE key_hash = %s
                    """,
                    (key_hash,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "key_id": row[0],
            "name": row[1],
            "api_key": row[2],
            "key_hash": row[3],
            "key_prefix": row[4],
            "enabled": bool(row[5]),
            "metadata": json.loads(row[6] or "{}"),
            "last_used_at": row[7],
            "created_at": row[8],
            "updated_at": row[9],
        }

    def record_api_key_usage(
        self,
        key_id: str,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        request_count: int = 1,
        success: bool = True,
        recorded_at: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if self._backend == "sqlite":
            return self._sqlite.record_api_key_usage(
                key_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                request_count=request_count,
                success=success,
                recorded_at=recorded_at,
                metadata=metadata,
            )
        ts = _state_db._ensure_iso(recorded_at)
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO api_key_usage_events (
                        key_id, recorded_at, input_tokens, output_tokens, request_count, success_count, failure_count, metadata_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        key_id,
                        ts,
                        int(input_tokens),
                        int(output_tokens),
                        max(0, int(request_count)),
                        max(0, int(request_count)) if success else 0,
                        max(0, int(request_count)) if not success else 0,
                        _dumps(metadata or {}),
                    ),
                )
                cur.execute(
                    """
                    UPDATE api_keys
                    SET last_used_at = %s, updated_at = %s
                    WHERE key_id = %s
                    """,
                    (ts, _utcnow_iso(), key_id),
                )

    def get_api_key_usage_summary(self, *, hours: int | None = None) -> dict[str, Any]:
        if self._backend == "sqlite":
            return self._sqlite.get_api_key_usage_summary(hours=hours)
        params: list[Any] = []
        where_clause = ""
        if hours is not None:
            cutoff = datetime.now(timezone.utc).timestamp() - (max(1, int(hours)) * 3600)
            where_clause = "AND EXTRACT(EPOCH FROM (e.recorded_at::timestamptz)) >= %s"
            params.append(int(cutoff))
        sql = f"""
            SELECT
                k.key_id,
                k.name,
                k.api_key,
                k.key_prefix,
                k.enabled,
                k.last_used_at,
                COALESCE(SUM(e.input_tokens), 0) AS input_tokens,
                COALESCE(SUM(e.output_tokens), 0) AS output_tokens,
                COALESCE(SUM(e.request_count), 0) AS request_count,
                COALESCE(SUM(e.success_count), 0) AS success_count,
                COALESCE(SUM(e.failure_count), 0) AS failure_count
            FROM api_keys AS k
            LEFT JOIN api_key_usage_events AS e ON e.key_id = k.key_id {where_clause}
            GROUP BY k.key_id, k.name, k.api_key, k.key_prefix, k.enabled, k.last_used_at, k.created_at
            ORDER BY k.created_at DESC, k.key_id DESC
        """
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
        data = [
            {
                "key_id": row[0],
                "name": row[1],
                "api_key": row[2],
                "key_prefix": row[3],
                "enabled": bool(row[4]),
                "last_used_at": row[5],
                "input_tokens": int(row[6]),
                "output_tokens": int(row[7]),
                "request_count": int(row[8]),
                "success_count": int(row[9]),
                "failure_count": int(row[10]),
            }
            for row in rows
        ]
        return {
            "key_count": len(data),
            "active_key_count": sum(1 for item in data if item["enabled"]),
            "total_input_tokens": sum(item["input_tokens"] for item in data),
            "total_output_tokens": sum(item["output_tokens"] for item in data),
            "total_request_count": sum(item["request_count"] for item in data),
            "total_success_count": sum(item["success_count"] for item in data),
            "total_failure_count": sum(item["failure_count"] for item in data),
            "data": data,
        }

    @staticmethod
    def _bucketize_api_key_rows(
        rows: list[Any],
        granularity: str,
    ) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            recorded_at = str(row[1] or "")
            ts = _state_db._parse_iso(recorded_at)
            if ts is None:
                continue
            if granularity == "raw":
                bucket = ts.replace(microsecond=0)
            elif granularity == "hourly":
                bucket = ts.replace(minute=0, second=0, microsecond=0)
            else:
                bucket = ts.replace(hour=0, minute=0, second=0, microsecond=0)
            key = bucket.isoformat(timespec="seconds")
            if key not in grouped:
                grouped[key] = {
                    "timestamp": key,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "request_count": 0,
                    "success_count": 0,
                    "failure_count": 0,
                }
            grouped[key]["input_tokens"] += int(row[2] or 0)
            grouped[key]["output_tokens"] += int(row[3] or 0)
            grouped[key]["request_count"] += int(row[4] or 0)
            grouped[key]["success_count"] += int(row[5] or 0)
            grouped[key]["failure_count"] += int(row[6] or 0)
        return [grouped[k] for k in sorted(grouped)]

    def get_api_key_usage_history(
        self,
        *,
        key_id: str | None = None,
        hours: int | None = 24,
        granularity: str = "hourly",
    ) -> list[dict[str, Any]]:
        if self._backend == "sqlite":
            return self._sqlite.get_api_key_usage_history(
                key_id=key_id, hours=hours, granularity=granularity
            )
        if granularity not in {"raw", "hourly", "daily"}:
            raise ValueError("granularity must be raw, hourly, or daily")
        where: list[str] = []
        params: list[Any] = []
        if key_id:
            where.append("key_id = %s")
            params.append(key_id)
        if hours is not None:
            cutoff = datetime.now(timezone.utc).timestamp() - (max(1, int(hours)) * 3600)
            where.append("EXTRACT(EPOCH FROM (recorded_at::timestamptz)) >= %s")
            params.append(int(cutoff))
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        sql = f"""
            SELECT key_id, recorded_at, input_tokens, output_tokens, request_count, success_count, failure_count
            FROM api_key_usage_events{where_sql}
            ORDER BY recorded_at ASC, event_id ASC
        """
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
        return self._bucketize_api_key_rows(list(rows), granularity)

    def delete_account(self, entry_id: str) -> None:
        if self._backend == "sqlite":
            self._sqlite.delete_account(entry_id)
            return
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM accounts WHERE entry_id = %s", (entry_id,))
        if self._aux is not None:
            self._aux.delete_account(entry_id)

    def close(self) -> None:
        if self._backend == "sqlite" and self._sqlite is not None:
            self._sqlite.close()
        if self._aux is not None:
            self._aux.close()

    def __getattr__(self, name: str) -> Any:
        if self._backend == "postgres" and self._aux is not None and not name.startswith("_"):
            return getattr(self._aux, name)
        raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")

    # ---- oauth pkce sessions ----
    def upsert_oauth_pkce_session(self, state: str, *, verifier: str, redirect_uri: str, created_at: str | None = None, completed: bool = False) -> None:
        ts = created_at or _utcnow_iso()
        if self._backend == "sqlite":
            account = self._sqlite.get_account("__oauth_pkce_state__") or {}
            mapping = dict(account.get("metadata") or {})
            mapping[state] = {
                "verifier": verifier,
                "redirect_uri": redirect_uri,
                "created_at": ts,
                "completed": bool(completed),
            }
            self._sqlite.upsert_account(
                "__oauth_pkce_state__",
                status="disabled",
                metadata=mapping,
                quota={},
                usage={},
            )
            return
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO oauth_pkce_sessions (state, verifier, redirect_uri, created_at, completed)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT(state) DO UPDATE SET
                        verifier = EXCLUDED.verifier,
                        redirect_uri = EXCLUDED.redirect_uri,
                        created_at = EXCLUDED.created_at,
                        completed = EXCLUDED.completed
                    """,
                    (state, verifier, redirect_uri, ts, 1 if completed else 0),
                )

    def get_oauth_pkce_session(self, state: str) -> dict[str, Any] | None:
        if self._backend == "sqlite":
            account = self._sqlite.get_account("__oauth_pkce_state__") or {}
            mapping = dict(account.get("metadata") or {})
            item = mapping.get(state)
            if not isinstance(item, dict):
                return None
            return {
                "state": state,
                "verifier": str(item.get("verifier") or ""),
                "redirect_uri": str(item.get("redirect_uri") or ""),
                "created_at": str(item.get("created_at") or ""),
                "completed": bool(item.get("completed")),
            }
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT state, verifier, redirect_uri, created_at, completed
                    FROM oauth_pkce_sessions
                    WHERE state = %s
                    """,
                    (state,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "state": row[0],
            "verifier": row[1],
            "redirect_uri": row[2],
            "created_at": row[3],
            "completed": bool(row[4]),
        }

    def mark_oauth_pkce_completed(self, state: str) -> None:
        if self._backend == "sqlite":
            session = self.get_oauth_pkce_session(state)
            if not session:
                return
            self.upsert_oauth_pkce_session(
                state,
                verifier=session["verifier"],
                redirect_uri=session["redirect_uri"],
                created_at=session.get("created_at"),
                completed=True,
            )
            return
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE oauth_pkce_sessions SET completed = 1 WHERE state = %s", (state,))

    def delete_oauth_pkce_session(self, state: str) -> None:
        if self._backend == "sqlite":
            account = self._sqlite.get_account("__oauth_pkce_state__") or {}
            mapping = dict(account.get("metadata") or {})
            if state in mapping:
                mapping.pop(state, None)
                self._sqlite.upsert_account(
                    "__oauth_pkce_state__",
                    status="disabled",
                    metadata=mapping,
                    quota={},
                    usage={},
                )
            return
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM oauth_pkce_sessions WHERE state = %s", (state,))

    # ---- connector sessions ----
    def create_connector_session(self, session_id: str, *, token_hash: str, expires_at: str, remote_addr: str | None = None, created_at: str | None = None) -> None:
        created = created_at or _utcnow_iso()
        if self._backend == "sqlite":
            account = self._sqlite.get_account("__connector_sessions__") or {}
            mapping = dict(account.get("metadata") or {})
            mapping[session_id] = {
                "session_id": session_id,
                "token_hash": token_hash,
                "created_at": created,
                "expires_at": expires_at,
                "status": "pending",
                "remote_addr": remote_addr or "",
                "uploaded_entry_id": "",
                "uploaded_email": "",
                "error_text": "",
                "last_seen_at": created,
            }
            self._sqlite.upsert_account("__connector_sessions__", status="disabled", metadata=mapping, quota={}, usage={})
            return
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO connector_sessions (
                        session_id, token_hash, created_at, expires_at, status, remote_addr,
                        uploaded_entry_id, uploaded_email, error_text, last_seen_at
                    ) VALUES (%s, %s, %s, %s, 'pending', %s, '', '', '', %s)
                    ON CONFLICT(session_id) DO UPDATE SET
                        token_hash = EXCLUDED.token_hash,
                        created_at = EXCLUDED.created_at,
                        expires_at = EXCLUDED.expires_at,
                        status = 'pending',
                        remote_addr = EXCLUDED.remote_addr,
                        uploaded_entry_id = '',
                        uploaded_email = '',
                        error_text = '',
                        last_seen_at = EXCLUDED.last_seen_at
                    """,
                    (session_id, token_hash, created, expires_at, remote_addr or "", created),
                )

    def get_connector_session(self, session_id: str) -> dict[str, Any] | None:
        if self._backend == "sqlite":
            account = self._sqlite.get_account("__connector_sessions__") or {}
            mapping = dict(account.get("metadata") or {})
            item = mapping.get(session_id)
            return dict(item) if isinstance(item, dict) else None
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT session_id, token_hash, created_at, expires_at, status, remote_addr,
                           uploaded_entry_id, uploaded_email, error_text, last_seen_at
                    FROM connector_sessions
                    WHERE session_id = %s
                    """,
                    (session_id,),
                )
                row = cur.fetchone()
        if not row:
            return None
        return {
            "session_id": row[0],
            "token_hash": row[1],
            "created_at": row[2],
            "expires_at": row[3],
            "status": row[4],
            "remote_addr": row[5],
            "uploaded_entry_id": row[6],
            "uploaded_email": row[7],
            "error_text": row[8],
            "last_seen_at": row[9],
        }

    def update_connector_session(self, session_id: str, **fields: Any) -> None:
        existing = self.get_connector_session(session_id)
        if not existing:
            return
        merged = {**existing, **fields, "last_seen_at": _utcnow_iso()}
        if self._backend == "sqlite":
            account = self._sqlite.get_account("__connector_sessions__") or {}
            mapping = dict(account.get("metadata") or {})
            mapping[session_id] = merged
            self._sqlite.upsert_account("__connector_sessions__", status="disabled", metadata=mapping, quota={}, usage={})
            return
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE connector_sessions
                    SET status = %s,
                        uploaded_entry_id = %s,
                        uploaded_email = %s,
                        error_text = %s,
                        last_seen_at = %s
                    WHERE session_id = %s
                    """,
                    (
                        str(merged.get("status") or "pending"),
                        str(merged.get("uploaded_entry_id") or ""),
                        str(merged.get("uploaded_email") or ""),
                        str(merged.get("error_text") or ""),
                        str(merged.get("last_seen_at") or _utcnow_iso()),
                        session_id,
                    ),
                )
