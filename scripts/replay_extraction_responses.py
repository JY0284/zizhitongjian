"""Recover complete paid responses into the store without making API requests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from knowledge_store import ChunkExtraction, KnowledgeStore
from model.extraction import EntityRelationExtraction
from scripts.run_budgeted_extraction import exclusive_run, repair_source_quotes, validate_chunk
from scripts.smoke_deepseek_extraction import build_input, load_book
from zztj_pipeline.llm_json import extract_json_from_response


def recover(receipts: Path, store_dir: Path):
    book = load_book(PROJECT_ROOT / "adapted_book.json")
    segments = {(j["juan_index"], s["segment_index"]): s for j in book for s in j["segments"]}
    recovered = []
    with exclusive_run(store_dir / ".extraction.lock"):
        store = KnowledgeStore(str(store_dir))
        for path in sorted(receipts.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            inp = data["input"]
            if "juan_index" not in inp:
                continue
            juan, seg = inp["juan_index"], inp["segment_index"]
            start = int(re.match(r"\[(\d+)\]", inp["target_sentences"][0])[1])
            key = store._make_key(juan, seg, start)
            if key in store._processed_keys:
                continue
            choice = data["choices"][0]
            if choice["finish_reason"] != "stop":
                continue
            segment = segments[juan, seg]
            expected, sentences, end = build_input(segment, seg, start, 1, 5)
            if inp["target_sentences"] != expected["target_sentences"]:
                raise ValueError("Saved response source does not match the canonical book")
            extraction = EntityRelationExtraction.model_validate(extract_json_from_response(choice["message"]["content"]))
            for item in [*extraction.entities, *extraction.locations, *extraction.events, *extraction.relations]:
                item.juan_index, item.segment_index = juan, seg
            usage = data["usage"]
            chunk = ChunkExtraction(juan_index=juan, segment_index=seg,
                chunk_start_index=start, chunk_end_index=end, segment_start_time=segment["segment_start_time"],
                source_sentences=sentences, **extraction.model_dump(), model_name=data["model"],
                prompt_tokens=usage["prompt_tokens"], completion_tokens=usage["completion_tokens"],
                total_tokens=usage["total_tokens"], quality_notes=[f"Recovered offline from paid response {path.name}"])
            repair_source_quotes(chunk)
            try:
                validate_chunk(chunk)
            except ValueError as exc:
                print(f"Still invalid {key}: {exc}")
                continue
            store.save_chunk(chunk)
            recovered.append(key)
    return recovered


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--responses", type=Path, default=PROJECT_ROOT / "data/runs/responses")
    parser.add_argument("--store-dir", type=Path, default=PROJECT_ROOT / "data/store")
    args = parser.parse_args()
    print("Recovered without API calls:", recover(args.responses, args.store_dir))
