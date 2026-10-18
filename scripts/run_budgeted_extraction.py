#!/usr/bin/env python3
"""Run model extraction under a persistent CNY budget; no hidden retries."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from openai import OpenAI
from langchain_core.messages import AIMessage
from knowledge_extraction import extract_chunk, positive_int
from knowledge_store import KnowledgeStore
from scripts.smoke_deepseek_extraction import load_book, load_dotenv_if_present
from zztj_pipeline.budget import BudgetLedger, BudgetExhausted, token_cost, units


class ProviderRequestError(RuntimeError):
    """Sanitized failure; never expose a provider error body or credentials."""


class ProviderValidationError(ValueError):
    """Locally generated diagnostic containing no provider response or secrets."""


class BudgetedModel:
    def __init__(self, client, ledger, model, input_rate, output_rate, max_output, effort, receipts, stream=False):
        self.client, self.ledger, self.model_name = client, ledger, model
        self.input_rate, self.output_rate = input_rate, output_rate
        self.max_output, self.effort, self.receipts = max_output, effort, Path(receipts)
        self.receipts.mkdir(parents=True, exist_ok=True)
        self.stopped = threading.Event()
        self.context = threading.local()
        self.stream = stream

    def invoke(self, messages):
        if self.stopped.is_set():
            raise ProviderRequestError("Run stopped after an uncertain provider outcome")
        payload = [{"role": "system" if m.type == "system" else "user", "content": m.content} for m in messages]
        chunk_input = json.loads(payload[-1]["content"])
        feedback = getattr(self.context, "feedback", "")
        if feedback:
            chunk_input["validation_feedback"] = feedback
            payload[-1]["content"] = json.dumps(chunk_input, ensure_ascii=False)
        # UTF-8 bytes upper-bound text BPE tokens; add ample chat framing overhead.
        input_bound = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + 1024
        if input_bound > 200_000:
            raise ValueError("Input too large for this short-context price policy")
        request = self.ledger.reserve(
            json.dumps({"juan": chunk_input.get("juan_index"), "segment": chunk_input["segment_index"], "note": chunk_input["note"]}),
            token_cost(input_bound, self.max_output, self.input_rate, self.output_rate))
        try:
            stream_options = {"stream": True, "stream_options": {"include_usage": True}} if self.stream else {}
            raw = self.client.chat.completions.with_raw_response.create(
                model=self.model_name, messages=payload, max_completion_tokens=self.max_output,
                reasoning_effort=self.effort,
                extra_body={"thinking": {"type": "disabled" if self.effort == "none" else "enabled"}},
                response_format={"type": "json_object"},
                **stream_options,
            )
            if self.stream:
                from openai.types.chat import ChatCompletion
                content, finish, usage, model, response_id, created = [], None, None, None, None, 0
                with raw.parse() as chunks:
                    for chunk in chunks:
                        model, response_id, created = chunk.model, chunk.id, chunk.created
                        if chunk.usage is not None:
                            usage = chunk.usage
                        for choice in chunk.choices:
                            if choice.index != 0:
                                raise ProviderValidationError("Unexpected extra completion choice")
                            if choice.delta.content:
                                content.append(choice.delta.content)
                            if choice.finish_reason:
                                finish = choice.finish_reason
                if finish is None or usage is None:
                    raise ProviderValidationError("Stream ended without a finish reason and usage")
                response = ChatCompletion.model_validate({
                    "id": response_id, "created": created, "model": model, "object": "chat.completion",
                    "usage": usage.model_dump(), "choices": [{"index": 0, "finish_reason": finish,
                    "message": {"role": "assistant", "content": "".join(content)}}],
                })
            else:
                response = raw.parse()
            provider_request_id = raw.headers.get("x-oneapi-request-id") or raw.headers.get("x-request-id")
            usage = response.usage
            if usage is None or any(type(n) is not int or n < 0 for n in
                                    [usage.prompt_tokens, usage.completion_tokens]) or usage.prompt_tokens == 0:
                raise ProviderValidationError("Provider omitted trustworthy usage")
            if usage.prompt_tokens > input_bound or usage.completion_tokens > self.max_output:
                raise ProviderValidationError("Provider exceeded a reserved token bound")
            self.ledger.settle(request, token_cost(usage.prompt_tokens, usage.completion_tokens,
                                                   self.input_rate, self.output_rate),
                               usage.prompt_tokens, usage.completion_tokens,
                               provider_request_id)
            # Preserve the paid response before parsing, so it can be repaired offline.
            receipt = {"model": response.model, "reasoning_effort": self.effort, "stream": self.stream, "usage": usage.model_dump(),
                       "request_id": provider_request_id,
                       "input": chunk_input, "choices": [c.model_dump() for c in response.choices]}
            (self.receipts / f"{request}.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
            if response.model != self.model_name:
                raise ProviderValidationError("Provider returned an unexpected model identity")
            choice = response.choices[0]
            if choice.finish_reason != "stop" or not choice.message.content:
                raise ProviderValidationError("Provider did not return a complete JSON answer")
            return AIMessage(content=choice.message.content,
                             response_metadata={"token_usage": usage.model_dump()})
        except Exception as exc:
            diagnostic = str(exc) if isinstance(exc, ProviderValidationError) else type(exc).__name__
            self.ledger.unknown(request, diagnostic)
            # A transport/usage/config failure halts new dispatch, including retries.
            self.stopped.set()
            raise ProviderRequestError(diagnostic) from None


@contextmanager
def exclusive_run(path: Path):
    """The OS releases this single-run lock after normal exit or a crash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def publish(store_dir: Path):
    """Publish a locally validated snapshot; no model or geocoding calls."""
    from entity_resolution import load_and_resolve
    from scripts.validate_artifacts import validate_artifacts
    kb = load_and_resolve(str(store_dir), str(PROJECT_ROOT / "data/segment_year_index.json"))
    payload = kb.model_dump(mode="json")
    from zztj_pipeline.source_review import aligned_sources, ZISI_PASSAGES
    payload['source_passages'] = aligned_sources(store_dir)
    for key in ZISI_PASSAGES & payload['source_passages'].keys():
        if '子思' in payload['source_passages'][key]['original']:
            payload['source_passages'][key]['review_note'] = '译文中的缺字人名“孔”按文言对照中的“子思”识别；未改动原始抽取记录。'
    geocoding_cache = PROJECT_ROOT / "data/location_geocoding.json"
    if geocoding_cache.exists():
        from scripts.merge_geocoding_into_unified_kb import merge_geocoding
        merge_geocoding(payload, json.loads(geocoding_cache.read_text(encoding="utf-8")))
    processed = sum(len(json.loads(p.read_text(encoding="utf-8"))) for p in store_dir.glob("juan_*.json"))
    total = sum(len(s["sentences"]) for j in load_book(PROJECT_ROOT / "adapted_book.json") for s in j["segments"])
    payload["data_source"] = str(store_dir.resolve().relative_to(PROJECT_ROOT)).replace("\\", "/")
    payload["extraction_models"] = sorted({chunk.get("model_name", "unknown")
        for path in store_dir.glob("juan_*.json")
        for chunk in json.loads(path.read_text(encoding="utf-8")).values()})
    book = load_book(PROJECT_ROOT / "adapted_book.json")
    coverage = []
    for juan in book:
        number = juan["juan_index"]
        path = store_dir / f"juan_{number}.json"
        count = len(json.loads(path.read_text(encoding="utf-8"))) if path.exists() else 0
        expected = sum(len(segment["sentences"]) for segment in juan["segments"])
        if count:
            coverage.append({"juan": number, "processed": count, "total": expected, "complete": count == expected})
    payload["data_coverage"] = coverage
    payload["data_notice"] = (
        f"模型抽取数据：已处理 {processed:,} / {total:,} 个原文片段，尚非全书知识库。"
        "已检查结构与引用；人物背景、史论边界和历史判断仍需人工审校。"
        if processed < total else "模型抽取数据：已检查结构与引用，历史内容仍需人工审校。"
    )
    year_index = json.loads((PROJECT_ROOT / "data/juan_year_index.json").read_text(encoding="utf-8"))
    segments = json.loads((PROJECT_ROOT / "data/segment_year_index.json").read_text(encoding="utf-8"))["segments"]
    ends = {}
    for segment in segments.values():
        year = segment.get("year")
        if isinstance(year, int):
            juan = str(segment["juan_index"])
            ends[juan] = max(ends.get(juan, year), year)
    year_index["juan_end_year"] = ends
    # Validation happens before either runtime file is replaced.
    with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "data") as stage:
        stage = Path(stage)
        atomic_json(stage / "unified_knowledge.json", payload)
        atomic_json(stage / "juan_year_index.json", year_index)
        errors = validate_artifacts(stage)
    if errors:
        raise ValueError(f"Unified knowledge validation failed: {errors[:3]}")
    for dest in [PROJECT_ROOT / "data/unified_knowledge.json",
                 PROJECT_ROOT / "visualization/public/data/unified_knowledge.json"]:
        atomic_json(dest, payload)
    atomic_json(PROJECT_ROOT / "visualization/public/data/juan_year_index.json",
                year_index)


def verify_price(base: str, args):
    """Check a privately configured price contract before spending."""
    from decimal import Decimal
    config_path = os.getenv("LLM_PRICING_CONFIG", "")
    if not config_path:
        raise ValueError("Configure LLM_PRICING_CONFIG before paid extraction")
    path = Path(config_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    contract = json.loads(path.read_text(encoding="utf-8"))
    if contract.get("base_url", "").rstrip("/") != base.rstrip("/"):
        raise ValueError("Price contract does not match the configured endpoint")
    model = contract.get("models", {}).get(args.model)
    if not model or contract.get("currency") != "CNY":
        raise ValueError("A reviewed CNY price contract is required for this model")
    group = contract["group"]
    units(str(contract["quota_per_unit"]))
    units(str(contract["usd_exchange_rate"]))
    for field in ["input_base_rate", "output_base_rate"]:
        units(str(model[field]))
    host = base.rstrip("/").removesuffix("/v1")
    def get(name):
        with urlopen(host + "/api/" + name, timeout=30) as response:
            return json.load(response)
    pricing, status = get("pricing"), get("status")["data"]
    row = next(r for r in pricing["data"] if r["model_name"] == args.model)
    if (status.get("quota_display_type") != contract["currency"]
        or status.get("usd_exchange_rate") != contract["usd_exchange_rate"]
        or status.get("quota_per_unit") != contract["quota_per_unit"]
        or row.get("billing_expr") != model["billing_expression"]
        or group not in row.get("enable_groups", [])):
        raise ValueError("Provider price contract changed; review it before spending")
    multiplier = Decimal(str(pricing["group_ratio"][group]))
    units(str(multiplier))
    if (Decimal(args.input_cny_per_million) < Decimal(str(model["input_base_rate"])) * multiplier
        or Decimal(args.output_cny_per_million) < Decimal(str(model["output_base_rate"])) * multiplier):
        raise ValueError("Configured rates do not cover the provider's current prices")
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "provider": host,
            "group": group, "group_ratio": str(multiplier), "price_row": row}


def atomic_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


def main(argv=None):
    load_dotenv_if_present(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--budget-cny", required=True, help="Total limit, retained when resuming this ledger")
    parser.add_argument("--input-cny-per-million", required=True, help="Conservative input rate, including cache writes")
    parser.add_argument("--output-cny-per-million", required=True)
    parser.add_argument("--ledger", type=Path, default=PROJECT_ROOT / "data/runs/terra-budget.sqlite3")
    parser.add_argument("--store-dir", type=Path, default=PROJECT_ROOT / "data/store")
    parser.add_argument("--prompt", type=Path, default=PROJECT_ROOT / "prompts/sys_entity_relation_extraction.md")
    parser.add_argument("--chunk-keys", type=Path, help="JSON list of juan-segment-sentence keys for evaluation")
    parser.add_argument("--no-publish", action="store_true", help="Keep evaluation/replacement data separate from the UI")
    parser.add_argument("--model", default="gpt-5.6-terra")
    parser.add_argument("--workers", type=positive_int, default=4)
    parser.add_argument("--max-output-tokens", type=positive_int, default=8192)
    parser.add_argument("--effort", choices=["none", "low", "medium", "high"], default="medium")
    parser.add_argument("--stream", action="store_true", help="Use SSE with final usage to reduce idle connection failures")
    parser.add_argument("--timeout-sec", type=positive_int, default=180, help="Provider network read timeout")
    parser.add_argument("--limit", type=positive_int)
    parser.add_argument("--juan-start", type=positive_int, default=1)
    parser.add_argument("--juan-end", type=positive_int, default=294)
    parser.add_argument("--publish-every", type=positive_int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    for value in [args.budget_cny, args.input_cny_per_million, args.output_cny_per_million]:
        units(value)
    base = os.getenv("LLM_BASE_URL", "")
    if not args.dry_run and (not os.getenv("LLM_API_KEY") or not base.startswith("https://")):
        parser.error("Configure LLM_API_KEY and an HTTPS LLM_BASE_URL in .env")
    if args.juan_start > args.juan_end:
        parser.error("Invalid volume range")
    book = [j for j in load_book(PROJECT_ROOT / "adapted_book.json")
            if args.juan_start <= j["juan_index"] <= args.juan_end]
    store = KnowledgeStore(str(args.store_dir))
    pending = store.get_unprocessed_chunks(book, chunk_size=1)
    if args.chunk_keys:
        requested = {tuple(map(int, key.split("-"))) for key in json.loads(args.chunk_keys.read_text(encoding="utf-8"))}
        pending = [key for key in pending if key in requested]
    selected = pending if args.limit is None else pending[:args.limit]
    print(f"Model={args.model}; pending={len(pending)}; selected={len(selected)}; budget CNY={args.budget_cny}", flush=True)
    if args.dry_run or not selected:
        return 0
    prompt = args.prompt.read_text(encoding="utf-8")
    identity = {"base_url": base, "model": args.model, "input_rate": args.input_cny_per_million,
                "output_rate": args.output_cny_per_million, "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
    segments = {(j["juan_index"], s["segment_index"]): s for j in book for s in j["segments"]}
    with exclusive_run(args.store_dir / ".extraction.lock"):
        ledger = BudgetLedger(args.ledger, args.budget_cny, identity)
        atomic_json(args.ledger.with_suffix(".pricing.json"), verify_price(base, args))
        with OpenAI(api_key=os.environ["LLM_API_KEY"], base_url=base, max_retries=0, timeout=args.timeout_sec) as client:
            model = BudgetedModel(client, ledger, args.model, args.input_cny_per_million,
                                  args.output_cny_per_million, args.max_output_tokens, args.effort,
                                  args.ledger.parent / "responses", stream=args.stream)
            saved = failures = 0
            status = "running"
            chunks = iter(selected)
            futures = {}
            stop_file = args.ledger.with_suffix(".stop")
            summary_file = args.ledger.with_suffix(".json")

            def report():
                result = {**ledger.summary(), "status": status, "saved_this_process": saved,
                          "failed_this_process": failures, "pid": os.getpid(),
                          "updated_at": datetime.now(timezone.utc).isoformat(),
                          "selected": len(selected), "processed_total": len(store._processed_keys)}
                atomic_json(summary_file, result)
                print(json.dumps(result, ensure_ascii=False), flush=True)

            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                def dispatch():
                    if stop_file.exists():
                        return
                    while len(futures) < args.workers and status == "running" and not model.stopped.is_set():
                        chunk = next(chunks, None)
                        if chunk is None:
                            break
                        futures[pool.submit(extract_validated_chunk, chunk, segments, model, prompt)] = chunk

                dispatch()
                report()
                while futures:
                    done, _ = wait(futures, return_when=FIRST_COMPLETED)
                    for future in done:
                        chunk = futures.pop(future)
                        try:
                            result = future.result()
                            repair_source_quotes(result)
                            validate_chunk(result)
                            store.save_chunk(result)
                            saved += 1
                            if saved % args.publish_every == 0 and not args.no_publish:
                                try:
                                    publish(args.store_dir)
                                    verify_price(base, args)
                                except Exception:
                                    model.stopped.set()
                                    raise
                        except BudgetExhausted:
                            status = "budget_exhausted"
                        except Exception as exc:
                            failures += 1
                            print(f"Failed {chunk}: {type(exc).__name__}: {str(exc)[:300]}", flush=True)
                            if model.stopped.is_set() or failures >= 5:
                                status = "stopped_on_error"
                        if stop_file.exists():
                            status = "stopped_by_file"
                    report()
                    dispatch()
            if status == "running":
                status = "stopped_by_file" if stop_file.exists() else ("completed_with_errors" if failures else "completed")
            try:
                if saved and not args.no_publish:
                    publish(args.store_dir)
            finally:
                report()
            return 1 if failures else 0


def result_as_extraction(result):
    from model.extraction import EntityRelationExtraction
    return EntityRelationExtraction(entities=result.entities, locations=result.locations,
                                    events=result.events, relations=result.relations)


def extract_validated_chunk(chunk, segments, model, prompt):
    """One bounded correction for a known invalid answer; every call is charged."""
    model.context.feedback = ""
    for attempt in range(2):
        try:
            result = extract_chunk(chunk, segments, model, prompt, 1, 5, 1)
            repair_source_quotes(result)
            validate_chunk(result)
            return result
        except (BudgetExhausted, ProviderRequestError):
            raise  # Never automatically repeat an uncertain paid request.
        except ValueError as exc:
            if attempt:
                raise
            model.context.feedback = (
                f"上次输出未通过校验：{str(exc)[:800]}。请重新提取目标句并检查所有引用。"
                "实体名必须一致，引用必须已定义；不能为了通过校验补造原文未出现的对象。"
                "缺少明确主动方/被动方时可使用空角色列表；所有句子索引必须是目标句索引。"
            )


def validate_chunk(result):
    """Validate provenance and graph references before marking a sentence done."""
    valid, errors = result_as_extraction(result).validate_relations()
    items = [*result.entities, *result.locations, *result.events, *result.relations]
    if not valid:
        raise ValueError("; ".join(errors))
    if any(not item.sentence_indexes_in_segment or
                        any(i != result.chunk_start_index for i in item.sentence_indexes_in_segment)
                        for item in items):
        raise ValueError("Invalid references or source sentence indexes")
    names = {name for e in result.entities for name in [e.name, *e.alias]}
    places = {name for loc in result.locations for name in [loc.name, *loc.alias]}
    event_names = {e.name for e in result.events}
    for event in result.events:
        if not set(event.participants) <= names or (event.location and event.location not in places):
            raise ValueError("Dangling event reference")
    for relation in result.relations:
        if ((relation.location and relation.location not in places) or
            (relation.event_name and relation.event_name not in event_names)):
            raise ValueError("Dangling relation reference")
    for location in result.locations:
        if not set(location.related_entities) <= names:
            raise ValueError("Dangling location reference")
    source = " ".join(result.source_sentences)
    for entity in result.entities:
        if entity.original_description_in_book and entity.original_description_in_book not in source:
            raise ValueError("Entity quotation is not present verbatim in the target sentence")


def repair_source_quotes(result):
    """Replace a paraphrased quote only when a named anchor exists in the source.

    This copies an exact source span without changing entities or inferred facts.
    The original paid response remains in the response receipt for audit.
    """
    source = " ".join(result.source_sentences)
    for entity in result.entities:
        quote = entity.original_description_in_book
        if quote and quote not in source:
            anchors = sorted([n for n in [entity.name, *entity.alias] if n and n in source], key=len, reverse=True)
            if not anchors:
                # An implicit referent may be valid, but its purported quotation is
                # not. Leave the quote empty and expose that uncertainty for review.
                entity.original_description_in_book = ""
                result.quality_notes.append(f"Unverified quotation removed; check implicit/contextual entity: {entity.name}")
                continue
            at = source.index(anchors[0])
            entity.original_description_in_book = source[max(0, at - 60): at + len(anchors[0]) + 100]
            result.quality_notes.append(f"Replaced non-verbatim quotation with an exact target-text span: {entity.name}")


if __name__ == "__main__":
    raise SystemExit(main())
