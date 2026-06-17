import sys

import pytest

from scripts import build_data


def test_build_data_skip_resolve_runs_deterministic_steps(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(build_data, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["build_data.py", "--skip-resolve"])

    commands: list[list[str]] = []
    monkeypatch.setattr(build_data, "run", commands.append)

    assert build_data.main() == 0

    assert commands == [
        [sys.executable, "scripts/build_segment_year_index.py", "--overrides", "data/segment_year_overrides.json"],
        [sys.executable, "scripts/build_juan_year_index.py"],
        [sys.executable, "scripts/validate_segment_year_index.py", "--fail"],
    ]
    assert "Skipping unified artifact validation" in capsys.readouterr().out


def test_build_data_requires_store_unless_resolve_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(build_data, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["build_data.py"])

    commands: list[list[str]] = []
    monkeypatch.setattr(build_data, "run", commands.append)

    with pytest.raises(SystemExit, match="data/store is missing"):
        build_data.main()

    assert commands == []


def test_build_data_requires_extraction_files_in_store(tmp_path, monkeypatch):
    (tmp_path / "data/store").mkdir(parents=True)
    monkeypatch.setattr(build_data, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["build_data.py"])

    commands: list[list[str]] = []
    monkeypatch.setattr(build_data, "run", commands.append)

    with pytest.raises(SystemExit, match="data/store contains no juan_\\*.json files"):
        build_data.main()

    assert commands == []


def test_build_data_publish_preflights_sources_before_copying(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/juan_year_index.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(build_data, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["build_data.py", "--skip-resolve", "--publish-frontend"])

    commands: list[list[str]] = []
    monkeypatch.setattr(build_data, "run", commands.append)

    with pytest.raises(SystemExit, match="data/unified_knowledge.json is missing"):
        build_data.main()

    assert not (tmp_path / "visualization/public/data/juan_year_index.json").exists()
