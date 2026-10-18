"""Check saved chunks against the book, without making any model requests."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from knowledge_store import ChunkExtraction
from scripts.smoke_deepseek_extraction import load_book
from scripts.run_budgeted_extraction import validate_chunk, atomic_json


def audit(book, store_dir, juan_end, model='gpt-5.6-terra'):
    errors, missing, coverage, notes = [], [], [], []
    counts = Counter()
    for juan in book:
        number = juan['juan_index']
        if number > juan_end:
            continue
        path = store_dir / f'juan_{number}.json'
        saved = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        expected = {}
        for segment in juan['segments']:
            for i, sentence in enumerate(segment['sentences']):
                expected[f"{number}-{segment['segment_index']}-{i}"] = (segment, i, sentence)
        missing.extend(sorted(set(expected) - set(saved)))
        for key in set(saved) - set(expected):
            errors.append({'chunk': key, 'error': 'Unexpected chunk key'})
        for key in set(saved) & set(expected):
            try:
                chunk = ChunkExtraction.model_validate(saved[key])
                segment, i, sentence = expected[key]
                assert (chunk.juan_index, chunk.segment_index, chunk.chunk_start_index, chunk.chunk_end_index) == (number, segment['segment_index'], i, i + 1), 'Incorrect chunk provenance'
                assert chunk.source_sentences == [sentence], 'Source does not match canonical book text'
                assert chunk.segment_start_time == segment['segment_start_time'], 'Wrong segment time'
                assert chunk.model_name == model, 'Unexpected model'
                for item in [*chunk.entities, *chunk.locations, *chunk.events, *chunk.relations]:
                    assert (item.juan_index, item.segment_index) == (number, segment['segment_index']), 'Wrong item provenance'
                validate_chunk(chunk)
                counts['valid_chunks'] += 1
                counts['raw_entities'] += len(chunk.entities)
                counts['raw_locations'] += len(chunk.locations)
                counts['raw_events'] += len(chunk.events)
                counts['raw_relations'] += len(chunk.relations)
                counts['commentary_relations'] += sum(action.is_commentary for action in chunk.relations)
                if chunk.quality_notes:
                    notes.append({'chunk': key, 'notes': chunk.quality_notes})
            except (ValueError, AssertionError) as error:
                errors.append({'chunk': key, 'error': str(error)})
        coverage.append({'juan': number, 'expected': len(expected), 'saved': len(set(saved) & set(expected))})
    return {'checked_at': datetime.now(timezone.utc).isoformat(), 'coverage': coverage,
            'counts': dict(counts), 'missing': missing, 'errors': errors,
            'chunks_with_quality_notes': len(notes), 'quality_notes': notes,
            'limitations': ['结构、原文与引用校验不能替代历史事实审校；机器生成的背景、史论分类和古今地名仍需复核。']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--juan-end', type=int, default=5)
    parser.add_argument('--store-dir', type=Path, default=ROOT / 'data/store')
    parser.add_argument('--model', default='gpt-5.6-terra')
    parser.add_argument('--out', type=Path, default=ROOT / 'data/runs/first-five-audit.json')
    args = parser.parse_args()
    result = audit(load_book(ROOT / 'adapted_book.json'), args.store_dir, args.juan_end, args.model)
    atomic_json(args.out, result)
    print(json.dumps({k: v for k, v in result.items() if k not in {'quality_notes', 'missing', 'errors'}}, ensure_ascii=False))
    print(f"Missing={len(result['missing'])}, errors={len(result['errors'])}; report={args.out}")
    return 1 if result['missing'] or result['errors'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
