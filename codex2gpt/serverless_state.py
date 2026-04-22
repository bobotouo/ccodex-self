"""State adapter for serverless runtime.

Uses Postgres when DATABASE_URL/POSTGRES_URL is configured, otherwise falls back
to local sqlite RuntimeStateStore.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

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
        else:
            runtime_root = os.path.abspath(os.environ.get("LITE_RUNTIME_ROOT", "/tmp/codex2gpt-runtime"))
            state_db_path = os.path.abspath(os.environ.get("LITE_STATE_DB", os.path.join(runtime_root, "state.sqlite3")))
            self._sqlite = RuntimeStateStore(state_db_path)
            self._backend = "sqlite"
            self._psycopg = None

    @property
    def backend(self) -> str:
        return self._backend

    def _pg_conn(self):
        return self._psycopg.connect(self.database_url, autocommit=True)

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

    def upsert_account(self, entry_id: str, **fields: Any) -> dict[str, Any]:
        if self._backend == "sqlite":
            return self._sqlite.upsert_account(entry_id, **fields)
        now = _utcnow_iso()
        with self._pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT created_at FROM accounts WHERE entry_id = %s", (entry_id,))
                row = cur.fetchone()
                created_at = row[0] if row else now
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
                        fields.get("auth_file"),
                        fields.get("email"),
                        fields.get("user_id"),
                        fields.get("account_id"),
                        fields.get("plan_type"),
                        fields.get("status", "active"),
                        fields.get("refresh_token"),
                        fields.get("proxy_id"),
                        fields.get("last_error"),
                        _dumps(fields.get("metadata", {})),
                        _dumps(fields.get("quota", {})),
                        _dumps(fields.get("usage", {})),
                        _dumps(fields.get("auth_payload", {})),
                        created_at,
                        now,
                    ),
                )
        accounts = self.list_accounts()
        return next((item for item in accounts if item["entry_id"] == entry_id), {})

    def list_proxies(self) -> list[dict[str, Any]]:
        if self._backend == "sqlite":
            return self._sqlite.list_proxies()
        return []

    def list_relay_providers(self, enabled_only: bool = False) -> list[dict[str, Any]]:
        if self._backend == "sqlite":
            return self._sqlite.list_relay_providers(enabled_only=enabled_only)
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
                    (key_id, name, api_key, key_hash, key_prefix, enabled, _dumps(metadata or {}), now, now),
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
