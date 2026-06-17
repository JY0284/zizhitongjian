import json
from pathlib import Path

from scripts.validate_artifacts import validate_artifacts


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def minimal_kb() -> dict:
    return {
        "roles": {
            "赵襄子": {
                "id": "赵襄子",
                "canonical_name": "赵襄子",
                "all_names": ["赵襄子"],
                "juans_appeared": [1],
            }
        },
        "locations": {
            "晋阳": {
                "id": "晋阳",
                "canonical_name": "晋阳",
                "coordinates": [112.5489, 37.8706],
                "juans_appeared": [1],
            }
        },
        "events": {
            "晋阳之战": {
                "id": "晋阳之战",
                "name": "晋阳之战",
                "time_start": -453,
                "time_end": -453,
                "source_juans": [1],
            }
        },
        "relations": {
            "智伯->赵襄子": {
                "id": "智伯->赵襄子",
                "from_entity": "智伯",
                "to_entity": "赵襄子",
                "first_interaction_year": -453,
                "last_interaction_year": -453,
                "source_juans": [1],
            }
        },
        "name_to_role_id": {"赵襄子": "赵襄子"},
        "name_to_location_id": {"晋阳": "晋阳"},
        "power_to_roles": {},
        "juan_to_roles": {"1": ["赵襄子"]},
        "juan_to_events": {"1": ["晋阳之战"]},
        "total_roles": 1,
        "total_locations": 1,
        "total_events": 1,
        "total_relations": 1,
        "juans_processed": [1],
    }


def test_validate_artifacts_accepts_minimal_runtime_data(tmp_path):
    write_json(tmp_path / "unified_knowledge.json", minimal_kb())
    write_json(
        tmp_path / "juan_year_index.json",
        {"version": "v1", "generated_at": "2026-01-01T00:00:00", "juan_start_year": {"1": -403}},
    )

    errors = validate_artifacts(tmp_path)

    assert errors == []


def test_validate_artifacts_reports_bad_coordinates(tmp_path):
    kb = minimal_kb()
    kb["locations"]["晋阳"]["coordinates"] = [37.8706, 112.5489]
    write_json(tmp_path / "unified_knowledge.json", kb)
    write_json(
        tmp_path / "juan_year_index.json",
        {"version": "v1", "generated_at": "2026-01-01T00:00:00", "juan_start_year": {"1": -403}},
    )

    errors = validate_artifacts(tmp_path)

    assert any("coordinates look like [lat, lng]" in error for error in errors)


def test_validate_artifacts_reports_missing_files(tmp_path):
    errors = validate_artifacts(tmp_path)

    assert "missing unified_knowledge.json" in errors
    assert "missing juan_year_index.json" in errors
