"""Durable, conservative API spend reservations (integer nano-CNY).

A request is charged its full reservation until authoritative token usage is
available. Failed requests, interrupted processes, and malformed usage never
refund the reservation. Reopening the same ledger retains all prior spend.
"""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal, ROUND_CEILING
import json
from pathlib import Path
import sqlite3
import time
import uuid

SCALE = 1_000_000_000


class BudgetExhausted(RuntimeError):
    pass


def units(value) -> int:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount <= 0:
        raise ValueError("Budget and rates must be finite and positive")
    return int((amount * SCALE).to_integral_value(rounding=ROUND_CEILING))


class BudgetLedger:
    def __init__(self, path: Path, budget_cny, identity: dict):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.budget = units(budget_cny)
        self.identity = json.dumps(identity, sort_keys=True)
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY, budget INTEGER, identity TEXT)")
            db.execute("""CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY, chunk TEXT, started REAL, reserved INTEGER,
                charged INTEGER, status TEXT, input_tokens INTEGER, output_tokens INTEGER,
                request_id TEXT, error TEXT)""")
            db.execute("INSERT OR IGNORE INTO config VALUES (1, ?, ?)", (self.budget, self.identity))
            config = db.execute("SELECT budget, identity FROM config WHERE id=1").fetchone()
            if config != (self.budget, self.identity):
                raise ValueError("Existing budget ledger has a different limit or pricing/model identity")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, chunk: str, amount: int) -> str:
        if amount <= 0:
            raise ValueError("Reservation must be positive")
        request = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            spent = db.execute("SELECT COALESCE(SUM(charged),0) FROM requests").fetchone()[0]
            if spent + amount > self.budget:
                raise BudgetExhausted("Insufficient remaining budget for the next request's maximum cost")
            db.execute("INSERT INTO requests VALUES (?, ?, ?, ?, ?, 'reserved', NULL, NULL, NULL, NULL)",
                       (request, chunk, time.time(), amount, amount))
        return request

    def settle(self, request: str, amount: int, input_tokens: int, output_tokens: int, request_id=None):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT reserved, status FROM requests WHERE id=?", (request,)).fetchone()
            if not row or row[1] != "reserved":
                raise ValueError("Reservation is missing or already finalized")
            if amount < 0 or amount > row[0]:
                # Keep the maximum reservation and stop the caller on a broken bound.
                raise ValueError("Reported usage exceeds the request's reserved cost")
            db.execute("UPDATE requests SET charged=?, status='settled', input_tokens=?, output_tokens=?, request_id=? WHERE id=?",
                       (amount, input_tokens, output_tokens, request_id, request))

    def unknown(self, request: str, error: str):
        with self.connect() as db:
            db.execute("UPDATE requests SET status='unknown', error=? WHERE id=? AND status='reserved'", (error, request))

    def summary(self) -> dict:
        with self.connect() as db:
            rows = db.execute("SELECT status, COUNT(*), SUM(charged), COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) FROM requests GROUP BY status").fetchall()
        used = sum(row[2] for row in rows)
        return {"budget_cny": self.budget / SCALE, "accounted_cny": used / SCALE,
                "remaining_cny": (self.budget - used) / SCALE,
                "requests": sum(row[1] for row in rows),
                "statuses": {row[0]: row[1] for row in rows},
                "input_tokens": sum(row[3] for row in rows),
                "output_tokens": sum(row[4] for row in rows)}


def token_cost(input_tokens: int, output_tokens: int, input_rate, output_rate) -> int:
    # One provider quota unit covers per-request rounding in addition to tokens.
    return int(((Decimal(input_tokens) * Decimal(str(input_rate)) +
                 Decimal(output_tokens) * Decimal(str(output_rate))) *
                Decimal(SCALE) / 1_000_000).to_integral_value(rounding=ROUND_CEILING)) + 2000
