import json

import pytest

from scripts.prepare_demo import prepare_demo
from scripts.validate_artifacts import validate_artifacts


def test_repository_sample_can_be_previewed_without_fabricated_data(tmp_path):
    payload = prepare_demo(tmp_path)
    assert payload["data_mode"] == "demo"
    assert payload["total_roles"] > 0
    assert payload["total_relations"] > 0
    assert payload["roles"]["吴起"]["description"]
    assert payload["events"] == {}
    assert payload["locations"] == {}
    assert validate_artifacts(tmp_path) == []
    assert prepare_demo(tmp_path)["total_roles"] == payload["total_roles"]


def test_demo_preserves_existing_runtime_data(tmp_path):
    path = tmp_path / "unified_knowledge.json"
    original = json.dumps({"roles": {"real": {}}})
    path.write_text(original, encoding="utf-8")
    with pytest.raises(ValueError, match="non-demo"):
        prepare_demo(tmp_path)
    assert path.read_text(encoding="utf-8") == original
    assert not (tmp_path / "juan_year_index.json").exists()
