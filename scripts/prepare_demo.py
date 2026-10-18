#!/usr/bin/env python3
"""Publish the repository's legacy sample for an offline UI preview.

The sample has no reliable volume/sentence provenance. Volume 1 is a display
bucket only; no events, coordinates, or inferred years are invented.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from entity_resolution import EntityResolver
from model.extraction import EntityRelationExtraction
from scripts.validate_artifacts import validate_artifacts


def prepare_demo(output: Path) -> dict:
    kb_path = output / "unified_knowledge.json"
    year_path = output / "juan_year_index.json"
    for path in (kb_path, year_path):
        if path.exists():
            previous = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(previous, dict) or previous.get("data_mode") != "demo":
                raise ValueError(f"Refusing to overwrite non-demo data: {path}")

    extraction = EntityRelationExtraction.model_validate_json(
        (PROJECT_ROOT / "data/demo_er.json").read_text(encoding="utf-8")
    )
    resolver = EntityResolver()
    for role in extraction.entities:
        resolver.add_role(role, 1, 0, 0, "")
    for relation in extraction.relations:
        relation.juan_index = 1
        resolver.add_relation(relation)
    kb = resolver.build_knowledge_base()
    payload = json.loads(kb.model_dump_json())
    payload.update(
        data_mode="demo",
        data_source="data/demo_er.json",
        data_notice="仓库样例：仅供关系网络与势力分布预览。卷 1 为展示分组，非原文定位；样例没有独立事件、地点或坐标。",
    )
    # A null year avoids assigning historical dates to this synthetic grouping.
    year_index = {"version": "v1", "data_mode": "demo", "generated_at": datetime.now(timezone.utc).isoformat(),
                  "juan_start_year": {"1": None}}
    output.mkdir(parents=True, exist_ok=True)
    kb_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    year_path.write_text(json.dumps(year_index, ensure_ascii=False, indent=2), encoding="utf-8")
    errors = validate_artifacts(output)
    if errors:
        raise ValueError("; ".join(errors))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "visualization/public/data")
    args = parser.parse_args()
    try:
        payload = prepare_demo(args.output)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"{exc}\n")
    print(f"Demo ready: {payload['total_roles']} roles, {payload['total_relations']} relations; {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
