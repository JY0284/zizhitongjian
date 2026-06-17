#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_coordinates(location_id: str, coords: Any) -> list[str]:
    if coords is None:
        return []
    if not isinstance(coords, list) or len(coords) != 2:
        return [f"location {location_id}: coordinates must be [lng, lat] or null"]
    lng, lat = coords
    if not is_number(lng) or not is_number(lat):
        return [f"location {location_id}: coordinates must contain numbers"]
    if 15 <= lng <= 55 and 70 <= lat <= 140:
        return [f"location {location_id}: coordinates look like [lat, lng], expected [lng, lat]"]
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        return [f"location {location_id}: coordinates out of valid range"]
    return []


def validate_relation_years(relation_id: str, relation: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    first = relation.get("first_interaction_year")
    last = relation.get("last_interaction_year")
    if first is not None and not isinstance(first, int):
        errors.append(f"relation {relation_id}: first_interaction_year must be int or null")
    if last is not None and not isinstance(last, int):
        errors.append(f"relation {relation_id}: last_interaction_year must be int or null")
    if isinstance(first, int) and isinstance(last, int) and first > last:
        errors.append(f"relation {relation_id}: first_interaction_year is after last_interaction_year")
    return errors


def validate_artifacts(data_dir: Path) -> list[str]:
    errors: list[str] = []
    kb_path = data_dir / "unified_knowledge.json"
    juan_path = data_dir / "juan_year_index.json"

    if not kb_path.exists():
        errors.append("missing unified_knowledge.json")
    if not juan_path.exists():
        errors.append("missing juan_year_index.json")
    if errors:
        return errors

    kb = load_json(kb_path)
    juan_index = load_json(juan_path)

    for key in ["roles", "locations", "events", "relations", "name_to_role_id", "name_to_location_id"]:
        if not isinstance(kb.get(key), dict):
            errors.append(f"unified_knowledge.json: {key} must be an object")

    if not isinstance(juan_index.get("juan_start_year"), dict):
        errors.append("juan_year_index.json: juan_start_year must be an object")

    for loc_id, location in (kb.get("locations") or {}).items():
        if not isinstance(location, dict):
            errors.append(f"location {loc_id}: must be an object")
            continue
        errors.extend(validate_coordinates(loc_id, location.get("coordinates")))

    for relation_id, relation in (kb.get("relations") or {}).items():
        if not isinstance(relation, dict):
            errors.append(f"relation {relation_id}: must be an object")
            continue
        errors.extend(validate_relation_years(relation_id, relation))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke validate frontend runtime data artifacts")
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing unified_knowledge.json and juan_year_index.json",
    )
    args = parser.parse_args()

    errors = validate_artifacts(Path(args.data_dir))
    if not errors:
        print("OK: artifact smoke validation passed")
        return 0

    print(f"Found {len(errors)} artifact validation error(s):")
    for error in errors:
        print(f"- {error}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
