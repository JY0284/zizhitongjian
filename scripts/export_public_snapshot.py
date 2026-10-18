"""Export the reviewed, read-only frontend data; never copy local run state."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.validate_artifacts import validate_artifacts

PUBLIC_FIELDS = {
    'roles', 'locations', 'events', 'relations', 'polities', 'organizations', 'schools',
    'name_to_role_id', 'name_to_location_id', 'name_to_polity_id', 'name_to_organization_id',
    'name_to_school_id', 'power_to_roles', 'juan_to_roles', 'juan_to_events', 'juan_to_polities',
    'juan_to_organizations', 'juan_to_schools', 'total_roles', 'total_locations', 'total_events',
    'total_relations', 'total_polities', 'total_organizations', 'total_schools', 'juans_processed',
    'last_updated', 'data_notice', 'data_coverage', 'extraction_models', 'source_passages',
}
PRIVATE_KEYS = {'api_key', 'authorization', 'password', 'access_token', 'refresh_token',
                'llm_api_key', 'amap_key'}


def check_public(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key.lower() in PRIVATE_KEYS or key.lower().endswith('_api_key'):
                raise ValueError('Credential field found in public data')
            check_public(item)
    elif isinstance(value, list):
        for item in value:
            check_public(item)
    elif isinstance(value, str):
        if re.search(r'https?://(?:localhost|127\.0\.0\.1|10\.\d+\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)', value, re.I):
            raise ValueError('Private network URL found in public data')
        if re.search(r'\b[A-Za-z]:[\\/]', value):
            raise ValueError('Local machine path found in public data')


def export_snapshot(source: Path, output: Path):
    errors = validate_artifacts(source)
    if errors:
        raise ValueError(f'Invalid source artifacts: {errors[:3]}')
    kb = json.loads((source / 'unified_knowledge.json').read_text(encoding='utf-8'))
    coverage = kb.get('data_coverage', [])
    if {row['juan'] for row in coverage} != {1, 2, 3, 4, 5} or not all(row['complete'] for row in coverage):
        raise ValueError('This public snapshot requires all first five volumes')
    payload = {key: value for key, value in kb.items() if key in PUBLIC_FIELDS}
    payload['data_source'] = 'public/first-five-astra-high'
    year_index = json.loads((source / 'juan_year_index.json').read_text(encoding='utf-8'))
    output.mkdir(parents=True, exist_ok=True)
    manifest = {'version': 1, 'coverage': coverage, 'models': kb['extraction_models'], 'files': {}}
    for name, data in [('unified_knowledge.json', payload), ('juan_year_index.json', year_index)]:
        check_public(data)
        encoded = (json.dumps(data, ensure_ascii=False, separators=(',', ':'), sort_keys=True) + '\n').encode('utf-8')
        (output / name).write_bytes(encoded)
        manifest['files'][name] = {'sha256': hashlib.sha256(encoded).hexdigest(), 'bytes': len(encoded)}
    (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    errors = validate_artifacts(output)
    if errors:
        raise ValueError(f'Invalid exported artifacts: {errors[:3]}')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'visualization/public/data')
    parser.add_argument('--out', type=Path, default=ROOT / 'visualization/snapshot')
    args = parser.parse_args()
    print(json.dumps(export_snapshot(args.source, args.out), ensure_ascii=False))
