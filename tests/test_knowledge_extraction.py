import json
import threading
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import knowledge_extraction as runner
from scripts.smoke_deepseek_extraction import build_input


def book_file(tmp_path):
    path = tmp_path / "book.json"
    path.write_text(json.dumps([{"juan_index": 1, "segments": [
        {"segment_index": 1, "segment_start_time": "前403年", "sentences": ["甲", "乙", "丙"]}
    ]}]), encoding="utf-8")
    return path


def test_dry_run_needs_no_key_and_makes_no_requests(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(runner, "load_dotenv_if_present", lambda _: None)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(runner, "ChatDeepSeek", lambda **_: pytest.fail("unexpected API client"))
    assert runner.main(["--dry-run", "--book", str(book_file(tmp_path)),
                        "--store-dir", str(tmp_path / "store")]) == 0
    assert "Pending: 3 chunks; selected: 1" in capsys.readouterr().out


def test_concurrent_requests_are_saved_on_main_thread_and_resume(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only")
    monkeypatch.setattr(runner, "load_dotenv_if_present", lambda _: None)
    response = SimpleNamespace(content='{"entities": [], "relations": []}', response_metadata={})
    model = SimpleNamespace(model_name="test-model", invoke=lambda _: response)
    monkeypatch.setattr(runner, "ChatDeepSeek", lambda **_: model)
    save = runner.KnowledgeStore.save_chunk
    saved_threads = []

    def track_save(self, chunk):
        saved_threads.append(threading.get_ident())
        save(self, chunk)

    monkeypatch.setattr(runner.KnowledgeStore, "save_chunk", track_save)
    args = ["--book", str(book_file(tmp_path)), "--store-dir", str(tmp_path / "store"), "--all"]
    assert runner.main(args) == 0
    assert saved_threads == [threading.get_ident()] * 3
    assert runner.main(args) == 0
    assert len(saved_threads) == 3
    assert len(json.loads((tmp_path / "store/juan_1.json").read_text(encoding="utf-8"))) == 3


@pytest.mark.parametrize("start,size,context", [(-1, 1, 0), (1, 1, 0), (0, 0, 0), (0, 1, -1)])
def test_invalid_smoke_ranges_are_rejected(start, size, context):
    with pytest.raises(ValueError, match="Invalid chunk range"):
        build_input({"sentences": ["甲"]}, 1, start, size, context)


def test_failed_requests_return_nonzero_and_remain_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only")
    monkeypatch.setattr(runner, "load_dotenv_if_present", lambda _: None)

    def fail(_):
        raise TimeoutError("test timeout")

    monkeypatch.setattr(runner, "ChatDeepSeek", lambda **_: SimpleNamespace(model_name="test", invoke=fail))
    args = ["--book", str(book_file(tmp_path)), "--store-dir", str(tmp_path / "store"), "--attempts", "1"]
    assert runner.main(args) == 1
    assert not (tmp_path / "store/juan_1.json").exists()


def test_upgraded_deepseek_client_roundtrip_uses_only_local_server(monkeypatch):
    """Exercise the real SDK's request/response contract without a paid API call."""
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            requests.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            body = json.dumps({
                "id": "local-test", "object": "chat.completion", "created": 0, "model": "deepseek-v4-flash",
                "choices": [{"index": 0, "finish_reason": "stop", "message": {
                    "role": "assistant", "content": '{"entities": [], "relations": []}'}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        local_url = f"http://127.0.0.1:{server.server_port}/v1"
        model = runner.ChatDeepSeek(model="deepseek-v4-flash", api_key="local-test-only",
                                    api_base=local_url,
                                    timeout=5, max_retries=0, cache=False, disable_streaming=True)
        assert str(model.client._client.base_url).startswith(local_url + "/")
        chunk = runner.extract_chunk((1, 1, 0), {(1, 1): {
            "segment_start_time": "前403年", "sentences": ["甲"]}}, model, "Extract JSON", 1, 0, 1)
        assert chunk.total_tokens == 3
        assert chunk.source_sentences == ["甲"]
        assert requests[0]["model"] == "deepseek-v4-flash"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
