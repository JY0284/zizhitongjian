#!/usr/bin/env python3

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)


def copy_if_exists(src: Path, dst: Path) -> bool:
    if not src.exists():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic data artifacts and optionally publish frontend runtime data"
    )
    parser.add_argument(
        "--skip-resolve",
        action="store_true",
        help="Skip entity resolution; useful when data/store is absent",
    )
    parser.add_argument(
        "--geocode",
        action="store_true",
        help="Run Amap geocoding; requires AMAP_KEY in local .env or environment",
    )
    parser.add_argument(
        "--publish-frontend",
        action="store_true",
        help="Copy runtime artifacts into visualization/public/data",
    )
    args = parser.parse_args()

    store_dir = PROJECT_ROOT / "data/store"
    unified_path = PROJECT_ROOT / "data/unified_knowledge.json"

    if not args.skip_resolve and not store_dir.exists():
        raise SystemExit("data/store is missing. Run extraction first or pass --skip-resolve.")

    run([sys.executable, "scripts/build_segment_year_index.py", "--overrides", "data/segment_year_overrides.json"])
    run([sys.executable, "scripts/build_juan_year_index.py"])
    run([sys.executable, "scripts/validate_segment_year_index.py", "--fail"])

    if not args.skip_resolve:
        run(
            [
                sys.executable,
                "entity_resolution.py",
                "--store-dir",
                "data/store",
                "--output",
                "data/unified_knowledge.json",
            ]
        )

    if args.geocode:
        if not unified_path.exists():
            raise SystemExit("data/unified_knowledge.json is missing. Cannot geocode.")
        run([sys.executable, "scripts/geocode_locations_amap.py"])
        run([sys.executable, "scripts/merge_geocoding_into_unified_kb.py"])

    if unified_path.exists():
        run([sys.executable, "scripts/validate_artifacts.py", "--data-dir", "data"])
    else:
        print("Skipping unified artifact validation because data/unified_knowledge.json is missing.")

    if args.publish_frontend:
        frontend_data = PROJECT_ROOT / "visualization/public/data"
        copied_juan = copy_if_exists(PROJECT_ROOT / "data/juan_year_index.json", frontend_data / "juan_year_index.json")
        copied_kb = copy_if_exists(unified_path, frontend_data / "unified_knowledge.json")
        if not copied_juan:
            raise SystemExit("data/juan_year_index.json was not found after build.")
        if not copied_kb:
            raise SystemExit("data/unified_knowledge.json is missing. Cannot publish complete frontend runtime data.")
        run([sys.executable, "scripts/validate_artifacts.py", "--data-dir", "visualization/public/data"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
