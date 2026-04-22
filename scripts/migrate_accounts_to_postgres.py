#!/usr/bin/env python3
"""Import local runtime/accounts/*.json into Postgres-backed serverless state."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from typing import Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from codex2gpt.serverless_state import ServerlessStateStore


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate local auth account files to Postgres.")
    parser.add_argument("--auth-dir", default=os.environ.get("LITE_AUTH_DIR", "./runtime/accounts"))
    args = parser.parse_args()

    store = ServerlessStateStore()
    if store.backend != "postgres":
        raise SystemExit("DATABASE_URL/POSTGRES_URL is not configured; backend is not postgres.")

    auth_dir = os.path.abspath(args.auth_dir)
    if not os.path.isdir(auth_dir):
        raise SystemExit(f"Auth directory does not exist: {auth_dir}")

    imported = 0
    for name in sorted(os.listdir(auth_dir)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(auth_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as exc:
            print(f"skip {name}: failed to parse json ({exc})")
            continue

        tokens = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else {}
        id_claims = decode_jwt_payload(str(tokens.get("id_token") or ""))
        auth_claims = id_claims.get("https://api.openai.com/auth") if isinstance(id_claims.get("https://api.openai.com/auth"), dict) else {}
        profile = id_claims.get("https://api.openai.com/profile") if isinstance(id_claims.get("https://api.openai.com/profile"), dict) else {}
        email = str(payload.get("email") or id_claims.get("email") or profile.get("email") or "").strip()
        user_id = str(payload.get("user_id") or id_claims.get("sub") or auth_claims.get("user_id") or "").strip()
        account_id = str(tokens.get("account_id") or payload.get("account_id") or auth_claims.get("chatgpt_account_id") or "").strip()
        plan_type = str(payload.get("plan_type") or payload.get("plan") or auth_claims.get("chatgpt_plan_type") or "").strip()

        store.upsert_account(
            os.path.basename(path),
            auth_file=path,
            email=email,
            user_id=user_id,
            account_id=account_id,
            plan_type=plan_type,
            status="active",
            refresh_token=str(tokens.get("refresh_token") or ""),
            proxy_id=None,
            last_error=None,
            metadata={"source": "migration_script", "id_claims": id_claims},
            quota={},
            usage={"input_tokens": 0, "output_tokens": 0, "request_count": 0},
            auth_payload=payload,
        )
        imported += 1
        print(f"imported: {name}")

    print(f"done. imported={imported} from {auth_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

