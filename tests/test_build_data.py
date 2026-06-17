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
