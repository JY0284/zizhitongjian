#!/usr/bin/env python3
"""Run a bounded real DeepSeek extraction smoke test.

This intentionally processes only a small number of chunks so API credentials,
prompt/schema parsing, and KnowledgeStore writes can be verified without
starting a full-book extraction job.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_deepseek import ChatDeepSeek

from knowledge_store import ChunkExtraction, KnowledgeStore
from model.extraction import EntityRelationExtraction
from zztj_pipeline.llm_json import extract_json_from_response


def load_dotenv_if_present(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_book(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_chunk(book: list[dict], juan_index: int, segment_index: int, chunk_start: int) -> tuple[dict, dict]:
    juan_data = next(j for j in book if int(j["juan_index"]) == juan_index)
    segment_data = next(s for s in juan_data["segments"] if int(s["segment_index"]) == segment_index)
    return juan_data, segment_data


def build_input(segment_data: dict, segment_index: int, chunk_start: int, chunk_size: int, context_size: int) -> tuple[dict, list[str], int]:
    sentences = segment_data["sentences"]
    chunk_end = min(chunk_start + chunk_size, len(sentences))
    chunk_sentences = sentences[chunk_start:chunk_end]
    context_start = max(0, chunk_start - context_size)
    context_sentences = sentences[context_start:chunk_start]

    indexed_target_sentences = [f"[{chunk_start + idx}]{sentence}" for idx, sentence in enumerate(chunk_sentences)]
    indexed_context_sentences = [f"[{context_start + idx}]{sentence}" for idx, sentence in enumerate(context_sentences)]

    input_data = {
        "segment_index": segment_index,
        "segment_start_time": segment_data["segment_start_time"],
        "context_sentences": indexed_context_sentences,
        "target_sentences": indexed_target_sentences,
        "note": f"Processing sentences {chunk_start} to {chunk_end - 1} of {len(sentences)}.",
    }
    return input_data, chunk_sentences, chunk_end


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one bounded real DeepSeek extraction smoke")
    parser.add_argument("--book", default="adapted_book.json", help="Path to adapted book JSON")
    parser.add_argument("--prompt", default="prompts/sys_entity_relation_extraction.md", help="Path to extraction prompt")
    parser.add_argument("--store-dir", default="data/store", help="KnowledgeStore directory")
    parser.add_argument("--juan", type=int, default=1, help="Juan index to extract")
    parser.add_argument("--segment", type=int, default=1, help="Segment index to extract")
    parser.add_argument("--chunk-start", type=int, default=0, help="Sentence index to start from")
    parser.add_argument("--chunk-size", type=int, default=1, help="Number of target sentences")
    parser.add_argument("--context-size", type=int, default=5, help="Number of preceding context sentences")
    parser.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"), help="DeepSeek model name")
    args = parser.parse_args()

    load_dotenv_if_present(PROJECT_ROOT / ".env")
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is missing. Add it to .env or export it before running.")

    book = load_book(PROJECT_ROOT / args.book)
    _, segment_data = find_chunk(book, args.juan, args.segment, args.chunk_start)
    input_data, chunk_sentences, chunk_end = build_input(
        segment_data,
        args.segment,
        args.chunk_start,
        args.chunk_size,
        args.context_size,
    )

    prompt = (PROJECT_ROOT / args.prompt).read_text(encoding="utf-8")
    chat_model = ChatDeepSeek(
        model=args.model,
        temperature=0.1,
        timeout=None,
        max_retries=0,
        api_key=api_key,
        cache=False,
        disable_streaming=True,
    )

    response = chat_model.invoke(
        [
            SystemMessage(prompt),
            HumanMessage(json.dumps(input_data, ensure_ascii=False, indent=2)),
        ]
    )
    extraction_data = extract_json_from_response(response.content)
    extraction = EntityRelationExtraction(**extraction_data)

    for entity in extraction.entities:
        entity.juan_index = args.juan
        entity.segment_index = args.segment
    for location in extraction.locations:
        location.juan_index = args.juan
        location.segment_index = args.segment
    for event in extraction.events:
        event.juan_index = args.juan
        event.segment_index = args.segment
    for relation in extraction.relations:
        relation.juan_index = args.juan
        relation.segment_index = args.segment

    usage = response.response_metadata.get("token_usage", {})
    chunk = ChunkExtraction(
        juan_index=args.juan,
        segment_index=args.segment,
        chunk_start_index=args.chunk_start,
        chunk_end_index=chunk_end,
        segment_start_time=segment_data["segment_start_time"],
        source_sentences=chunk_sentences,
        entities=extraction.entities,
        locations=extraction.locations,
        events=extraction.events,
        relations=extraction.relations,
        extracted_at=datetime.datetime.now().isoformat(),
        model_name=args.model,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
    )
    store = KnowledgeStore(store_dir=args.store_dir)
    store.save_chunk(chunk)

    print(
        "Saved smoke extraction "
        f"juan={args.juan} segment={args.segment} chunk_start={args.chunk_start} "
        f"entities={len(extraction.entities)} locations={len(extraction.locations)} "
        f"events={len(extraction.events)} relations={len(extraction.relations)} "
        f"model={args.model}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
