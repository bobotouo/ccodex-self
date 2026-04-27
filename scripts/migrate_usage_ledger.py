#!/usr/bin/env python3
"""Backfill usage_events from latest snapshot deltas."""

from __future__ import annotations

import argparse
import os
import sqlite3

from codex2gpt.state_db import RuntimeStateStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill usage_events from usage_snapshots deltas.")
    parser.add_argument("--db-path", required=True, help="Path to state sqlite database")
    parser.add_argument("--hours", type=int, default=24 * 30, help="History window in hours")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = os.path.abspath(args.db_path)
    store = RuntimeStateStore(db_path)
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cutoff = max(1, int(args.hours))
        rows = conn.execute(
            """
            SELECT account_id, captured_at, input_tokens, output_tokens, request_count
            FROM usage_snapshots
            WHERE strftime('%s', captured_at) >= strftime('%s', 'now') - (? * 3600)
            ORDER BY account_id ASC, captured_at ASC, snapshot_id ASC
            """,
            (cutoff,),
        ).fetchall()
        previous: dict[str, dict[str, int]] = {}
        inserted = 0
        for item in rows:
            account_id = str(item["account_id"] or "__unknown__")
            current = {
                "input_tokens": int(item["input_tokens"] or 0),
                "output_tokens": int(item["output_tokens"] or 0),
                "request_count": int(item["request_count"] or 0),
            }
            prior = previous.get(account_id)
            if prior is None:
                delta = current
            else:
                delta = {
                    key: max(0, current[key] - int(prior.get(key) or 0))
                    for key in current
                }
                for key in current:
                    if current[key] < int(prior.get(key) or 0):
                        delta[key] = current[key]
            previous[account_id] = current
            requests = int(delta["request_count"] or 0)
            if requests <= 0:
                continue
            store.append_usage_event(
                request_id=f"backfill::{item['captured_at']}::{account_id}::{inserted}",
                account_id=account_id,
                status="backfill",
                input_tokens=int(delta["input_tokens"] or 0),
                output_tokens=int(delta["output_tokens"] or 0),
                request_count=requests,
                source="backfill",
                recorded_at=str(item["captured_at"] or ""),
                metadata={"from": "usage_snapshots"},
            )
            inserted += 1
        conn.close()
        print(f"backfilled events: {inserted}")
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
