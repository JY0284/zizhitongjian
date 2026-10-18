"""Bounded, resumable knowledge extraction. Run --dry-run before a real batch."""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_deepseek import ChatDeepSeek

from knowledge_store import ChunkExtraction, KnowledgeStore
from model.extraction import EntityRelationExtraction
from scripts.smoke_deepseek_extraction import build_input, load_book, load_dotenv_if_present
from zztj_pipeline.llm_json import extract_json_from_response

PROJECT_ROOT = Path(__file__).resolve().parent


def positive_int(value: str) -> int:
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return result


def extract_chunk(chunk_info, segments, model, prompt, chunk_size, context_size, attempts):
    """Workers perform requests; the main thread alone persists their results."""
    juan, segment_index, start = chunk_info
    segment = segments[(juan, segment_index)]
    input_data, sentences, end = build_input(segment, segment_index, start, chunk_size, context_size)
    input_data["juan_index"] = juan
    input_data["source_constraints"] = (
        "事实字段仅根据目标句；上下文只用于消歧。未明示事件/动作发生地点时 location 必须为 JSON null，"
        "不能把人物所属国家或势力自动当作事件发生地。未知可选值用 JSON null，禁止字符串 None/null。"
        "所有 sentence_indexes_in_segment 只引用 target_sentences 的索引。"
        "original_description_in_book 必须是目标句中的逐字引文。背景知识仅放 description/background，"
        "不得据此新增原文没有的动作、参与者、时间或地点。"
    )
    for attempt in range(attempts):
        try:
            response = model.invoke([
                SystemMessage(prompt),
                HumanMessage(json.dumps(input_data, ensure_ascii=False)),
            ])
            extraction = EntityRelationExtraction.model_validate(extract_json_from_response(response.content))
            for item in [*extraction.entities, *extraction.locations, *extraction.events, *extraction.relations]:
                item.juan_index = juan
                item.segment_index = segment_index
            usage = response.response_metadata.get("token_usage", {})
            return ChunkExtraction(
                juan_index=juan, segment_index=segment_index,
                chunk_start_index=start, chunk_end_index=end,
                segment_start_time=segment["segment_start_time"], source_sentences=sentences,
                entities=extraction.entities, locations=extraction.locations,
                events=extraction.events, relations=extraction.relations,
                model_name=model.model_name,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            )
        except Exception:
            if attempt + 1 == attempts:
                raise
            time.sleep(min(2 ** attempt, 8))


def main(argv=None) -> int:
    load_dotenv_if_present(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--book", type=Path, default=PROJECT_ROOT / "adapted_book.json")
    parser.add_argument("--store-dir", type=Path, default=PROJECT_ROOT / "data/store")
    parser.add_argument("--juan-start", type=positive_int, default=1)
    parser.add_argument("--juan-end", type=positive_int, default=294)
    bounds = parser.add_mutually_exclusive_group()
    bounds.add_argument("--limit", type=positive_int, default=1, help="Maximum pending chunks (default: 1)")
    bounds.add_argument("--all", action="store_true", help="Process all pending chunks in the selected range")
    parser.add_argument("--workers", type=positive_int, default=4)
    parser.add_argument("--attempts", type=positive_int, default=3)
    parser.add_argument("--timeout", type=positive_int, default=120, help="Request timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Show pending work without API calls")
    parser.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"))
    args = parser.parse_args(argv)
    if args.juan_start > args.juan_end:
        parser.error("--juan-start must not exceed --juan-end")
    if not args.dry_run and not os.getenv("DEEPSEEK_API_KEY"):
        parser.error("DEEPSEEK_API_KEY is missing. Set it in .env or use --dry-run.")

    book = [j for j in load_book(args.book) if args.juan_start <= j["juan_index"] <= args.juan_end]
    if not book:
        parser.error("No volumes in the selected range")
    # Keep chunk size stable so cached sentence offsets retain their meaning.
    store = KnowledgeStore(str(args.store_dir))
    pending = store.get_unprocessed_chunks(book, chunk_size=1)
    selected = pending if args.all else pending[:args.limit]
    print(f"Pending: {len(pending)} chunks; selected: {len(selected)}; model: {args.model}")
    if args.dry_run or not selected:
        return 0

    segments = {(j["juan_index"], s["segment_index"]): s for j in book for s in j["segments"]}
    prompt = (PROJECT_ROOT / "prompts/sys_entity_relation_extraction.md").read_text(encoding="utf-8")
    model = ChatDeepSeek(model=args.model, api_key=os.environ["DEEPSEEK_API_KEY"],
                         temperature=0.1, timeout=args.timeout, max_retries=0,
                         cache=False, disable_streaming=True)
    failures = 0
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(extract_chunk, chunk, segments, model, prompt, 1, 5, args.attempts): chunk
            for chunk in selected
        }
        for future in as_completed(futures):
            try:
                store.save_chunk(future.result())
            except Exception as exc:
                failures += 1
                print(f"Failed {futures[future]}: {type(exc).__name__}: {exc}")
    print(f"Saved: {len(selected) - failures}; failed: {failures}. Rerun to resume pending chunks.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
