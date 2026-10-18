"""Read provider logs and reconcile this run only; never change its spend ledger."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import sys
from decimal import Decimal
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from scripts.smoke_deepseek_extraction import load_dotenv_if_present


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=PROJECT_ROOT / "data/runs/terra-budget.sqlite3")
    args = parser.parse_args()
    load_dotenv_if_present(PROJECT_ROOT / ".env")
    endpoint = os.environ.get("LLM_BILLING_LOG_URL", "")
    conversion = Decimal(os.environ.get("LLM_BILLING_UNITS_PER_CNY", "0"))
    if not endpoint.startswith("https://") or not conversion.is_finite() or conversion <= 0:
        parser.error("Configure an HTTPS LLM_BILLING_LOG_URL and positive LLM_BILLING_UNITS_PER_CNY")
    request = Request(endpoint, headers={"Authorization": "Bearer " + os.environ["LLM_API_KEY"]})
    with urlopen(request, timeout=30) as response:
        body = json.load(response)
    if body.get("success") is not True or not isinstance(body.get("data"), list):
        raise ValueError("Provider did not return token logs")
    logs = body["data"]
    with sqlite3.connect(args.ledger) as db:
        identity = json.loads(db.execute("SELECT identity FROM config WHERE id=1").fetchone()[0])
        local = db.execute("SELECT id,request_id,started,input_tokens,output_tokens,status FROM requests").fetchall()
    matches, unmatched, used = [], [], set()
    for rid, provider_id, started, inp, out, status in local:
        if status == "reserved":
            continue
        kind = "request_id"
        candidates = [r for r in logs if provider_id and r.get("request_id") == provider_id]
        receipt = args.ledger.parent / "responses" / f"{rid}.json"
        if not provider_id and receipt.exists() and inp is not None:
            # Older receipts lacked the gateway header. Keep this weaker match
            # explicitly labeled, and never use it to refund a reservation.
            kind = "unique_usage_and_time"
            candidates = [r for r in logs if r.get("model_name") == identity["model"]
                          and r.get("prompt_tokens") == inp and r.get("completion_tokens") == out
                          and started - 5 <= r.get("created_at", 0) <= receipt.stat().st_mtime + 5]
        if len(candidates) != 1 or candidates[0].get("request_id") in used:
            unmatched.append({"local_id": rid, "status": status})
            continue
        row = candidates[0]
        used.add(row.get("request_id"))
        matches.append({"local_id": rid, "provider_request_id": row.get("request_id"), "match": kind,
                        "quota": row["quota"], "cny": float(Decimal(str(row["quota"])) / conversion),
                        "group": row.get("group"), "model": row.get("model_name")})
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "matched": len(matches),
              "unmatched": unmatched, "exact_id_matches": sum(r["match"] == "request_id" for r in matches),
              "matched_provider_cny": float(sum(Decimal(str(r["quota"])) for r in matches) / conversion), "requests": matches}
    path = args.ledger.with_suffix(".reconciliation.json")
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "requests"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
