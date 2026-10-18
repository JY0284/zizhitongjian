import json
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

from langchain_core.messages import HumanMessage, SystemMessage
from openai import OpenAI
import pytest

from scripts.run_budgeted_extraction import BudgetedModel, ProviderRequestError, exclusive_run
from zztj_pipeline.budget import BudgetLedger, BudgetExhausted, token_cost, units


@pytest.mark.parametrize('failure', [None, 'changed_expression', 'rate_too_low', 'endpoint_mismatch'])
def test_private_price_contract_still_blocks_unreviewed_spend(tmp_path, monkeypatch, failure):
    from io import BytesIO
    from types import SimpleNamespace
    from scripts import run_budgeted_extraction as runner
    contract = {'base_url': 'https://example.invalid/v1', 'group': 'example', 'currency': 'CNY',
                'quota_per_unit': 1000, 'usd_exchange_rate': 1, 'models': {'test-model': {
                    'billing_expression': 'example-rule', 'input_base_rate': '2', 'output_base_rate': '4'}}}
    path = tmp_path / 'private-pricing.json'
    path.write_text(json.dumps(contract), encoding='utf-8')
    monkeypatch.setenv('LLM_PRICING_CONFIG', str(path))
    payloads = {'pricing': {'group_ratio': {'example': 1}, 'data': [{
        'model_name': 'test-model', 'enable_groups': ['example'],
        'billing_expr': 'changed' if failure == 'changed_expression' else 'example-rule'}]},
        'status': {'data': {'quota_display_type': 'CNY', 'quota_per_unit': 1000, 'usd_exchange_rate': 1}}}
    monkeypatch.setattr(runner, 'urlopen', lambda url, **kwargs: BytesIO(json.dumps(payloads[url.rsplit('/', 1)[-1]]).encode()))
    args = SimpleNamespace(model='test-model', input_cny_per_million='1' if failure == 'rate_too_low' else '2',
                           output_cny_per_million='4')
    endpoint = 'https://other.invalid/v1' if failure == 'endpoint_mismatch' else contract['base_url']
    if failure:
        with pytest.raises(ValueError):
            runner.verify_price(endpoint, args)
    else:
        assert runner.verify_price(endpoint, args)['group'] == 'example'


def test_paid_run_requires_private_price_configuration(monkeypatch):
    from scripts.run_budgeted_extraction import verify_price
    monkeypatch.delenv('LLM_PRICING_CONFIG', raising=False)
    with pytest.raises(ValueError, match='LLM_PRICING_CONFIG'):
        verify_price('https://example.invalid/v1', None)


def test_concurrent_reservations_and_resume_never_reset_the_budget(tmp_path):
    path = tmp_path / "budget.sqlite3"
    ledger = BudgetLedger(path, "1", {"model": "test"})
    def reserve(_):
        try:
            return ledger.reserve("chunk", units("0.3"))
        except BudgetExhausted:
            return None
    with ThreadPoolExecutor(max_workers=8) as pool:
        accepted = [r for r in pool.map(reserve, range(20)) if r]
    assert len(accepted) == 3
    ledger.unknown(accepted[0], "TimeoutError")
    reopened = BudgetLedger(path, "1", {"model": "test"})
    assert reopened.summary()["accounted_cny"] == 0.9
    with pytest.raises(BudgetExhausted):
        reopened.reserve("retry", units("0.2"))
    with pytest.raises(ValueError, match="different"):
        BudgetLedger(path, "2", {"model": "test"})


def test_usage_settlement_does_not_refund_more_than_reserved(tmp_path):
    ledger = BudgetLedger(tmp_path / "budget.sqlite3", "1", {})
    req = ledger.reserve("a", units("0.3"))
    with pytest.raises(ValueError, match="exceeds"):
        ledger.settle(req, units("0.4"), 1, 1)
    assert ledger.summary()["accounted_cny"] == 0.3
    ledger.settle(req, units("0.1"), 1, 1)
    with pytest.raises(ValueError, match="finalized"):
        ledger.settle(req, units("0.1"), 1, 1)
    assert ledger.summary()["accounted_cny"] == 0.1


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "0"])
def test_invalid_budget_or_rate(value):
    with pytest.raises(ValueError):
        units(value)


@pytest.mark.parametrize("mode", ["ok", "no_usage", "timeout", "stream_ok", "stream_no_usage", "stream_truncated"])
def test_real_sdk_calls_only_loopback_and_bills_unknown_results(tmp_path, monkeypatch, mode):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    received = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = {"id": "local", "object": "chat.completion", "created": 0, "model": "test",
                    "choices": [{"index": 0, "finish_reason": "stop", "message": {
                        "role": "assistant", "content": '{"entities":[],"relations":[]}'}}]}
            if mode != "no_usage":
                body["usage"] = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
            raw = json.dumps(body).encode()
            streaming = mode.startswith("stream_")
            if streaming:
                base = {"id": "local", "object": "chat.completion.chunk", "created": 0, "model": "test"}
                events = [{**base, "choices": [{"index": 0, "delta": {"role": "assistant", "content": '{"entities":[],'}, "finish_reason": None}]}]
                if mode != "stream_truncated":
                    events.append({**base, "choices": [{"index": 0, "delta": {"content": '"relations":[]}'}, "finish_reason": "stop"}]})
                if mode == "stream_ok":
                    events.append({**base, "choices": [], "usage": body["usage"]})
                raw = (''.join('data: ' + json.dumps(event) + '\n\n' for event in events) + 'data: [DONE]\n\n').encode()
            self.send_response(503 if mode == "timeout" else 200)
            self.send_header("Content-Type", "text/event-stream" if streaming else "application/json")
            self.send_header("x-oneapi-request-id", "provider-local-test")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    ledger = BudgetLedger(tmp_path / "budget.sqlite3", "30", {})
    try:
        url = f"http://127.0.0.1:{server.server_port}/v1"
        with OpenAI(api_key="local-test-only", base_url=url, max_retries=0) as client:
            assert str(client.base_url).startswith(url + "/")
            model = BudgetedModel(client, ledger, "test", "0.075", "0.36", 128, "medium", tmp_path / "responses", stream=mode.startswith('stream_'))
            messages = [SystemMessage("Extract JSON"), HumanMessage(json.dumps({"segment_index": 1, "note": "test"}))]
            if mode in {"ok", "stream_ok"}:
                result = model.invoke(messages)
                assert json.loads(result.content) == {"entities": [], "relations": []}
                assert result.response_metadata["token_usage"]["completion_tokens"] == 20
                assert ledger.summary()["accounted_cny"] == token_cost(10, 20, "0.075", "0.36") / 1e9
                assert len(list((tmp_path / "responses").glob("*.json"))) == 1
                receipt = json.loads(next((tmp_path / "responses").glob("*.json")).read_text(encoding="utf-8"))
                assert receipt["request_id"] == "provider-local-test"
            else:
                with pytest.raises(ProviderRequestError):
                    model.invoke(messages)
                assert ledger.summary()["statuses"] == {"unknown": 1}
                assert model.stopped.is_set()
            assert len(received) == 1  # No SDK retries, including server errors.
            assert received[0]["max_completion_tokens"] == 128
            assert received[0]["thinking"] == {"type": "enabled"}
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_second_writer_cannot_use_the_same_store(tmp_path):
    with exclusive_run(tmp_path / "lock"):
        with pytest.raises(OSError):
            with exclusive_run(tmp_path / "lock"):
                pytest.fail("concurrent store writer acquired the lock")


def test_unknown_strings_do_not_become_literal_places_or_powers():
    from model.role import Role
    from model.event import Event
    from model.action import Action
    assert Role(name="A", power="None").power is None
    assert Event(name="A", description="A", location="null").location is None
    assert Action(from_roles=["A"], to_roles=["B"], action="A", context="A", location="None").location is None


def test_paid_result_with_invented_quote_or_dangling_event_is_not_accepted():
    from scripts.run_budgeted_extraction import validate_chunk
    from knowledge_store import ChunkExtraction
    from model.role import Role
    from model.event import Event
    chunk = ChunkExtraction(juan_index=1, segment_index=1, chunk_start_index=0, chunk_end_index=1,
                            segment_start_time="前403", source_sentences=["A met B"],
                            entities=[Role(name="A", original_description_in_book="invented",
                                           sentence_indexes_in_segment=[0])])
    with pytest.raises(ValueError, match="quotation"):
        validate_chunk(chunk)
    chunk.entities[0].original_description_in_book = "A"
    validate_chunk(chunk)
    chunk.events = [Event(name="meeting", description="met", participants=["B"], sentence_indexes_in_segment=[0])]
    with pytest.raises(ValueError, match="Dangling"):
        validate_chunk(chunk)


def test_quote_repair_requires_a_verbatim_named_anchor():
    from scripts.run_budgeted_extraction import repair_source_quotes, validate_chunk
    from knowledge_store import ChunkExtraction
    from model.role import Role
    chunk = ChunkExtraction(juan_index=1, segment_index=1, chunk_start_index=0, chunk_end_index=1,
                            segment_start_time="前403", source_sentences=["A met B"],
                            entities=[Role(name="A", original_description_in_book="A met C",
                                           sentence_indexes_in_segment=[0])])
    repair_source_quotes(chunk)
    assert chunk.entities[0].original_description_in_book == "A met B"
    assert chunk.quality_notes
    validate_chunk(chunk)
    chunk.entities[0].name = "unknown"
    chunk.entities[0].original_description_in_book = "invented"
    repair_source_quotes(chunk)
    assert chunk.entities[0].original_description_in_book == ""
    assert "Unverified" in chunk.quality_notes[-1]
    validate_chunk(chunk)


def test_correction_is_bounded_and_includes_the_validation_error():
    from types import SimpleNamespace
    from scripts.run_budgeted_extraction import extract_validated_chunk
    calls = []
    model = SimpleNamespace(model_name="test", context=threading.local())
    def invoke(_):
        calls.append(model.context.feedback)
        answer = {"entities": [], "relations": []}
        if len(calls) == 1:
            answer["relations"] = [{"from_roles": ["missing"], "to_roles": [], "action": "a", "context": "a", "sentence_indexes_in_segment": [0]}]
        return SimpleNamespace(content=json.dumps(answer), response_metadata={})
    model.invoke = invoke
    result = extract_validated_chunk((1, 1, 0), {(1, 1): {"sentences": ["A"], "segment_start_time": "前403"}}, model, "Extract JSON")
    assert result.entities == []
    assert len(calls) == 2 and calls[0] == "" and "missing" in calls[1]
