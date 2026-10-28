"""Reaching Ollama through an authenticating gateway: the client sends the key, the gateway enforces it."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import gateway
from app.core.config import Settings
from app.core.errors import ServiceUnavailable
from app.services.embedding_service import PAYMENT, RATE_LIMITED, REJECTED, OllamaClient

KEY = "k" * 40


class _Resp:
    """Just enough of an httpx response for OllamaClient."""

    def __init__(self, status=200, data=None, lines=()):
        self.status, self.data, self.lines = status, data or {}, lines

    def raise_for_status(self):
        if self.status >= 400:
            raise httpx.HTTPStatusError("failed", request=httpx.Request("POST", "http://x"),
                                        response=httpx.Response(self.status, text="secret body"))

    def json(self):
        return self.data

    def iter_lines(self):
        return iter(self.lines)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def seen(monkeypatch):
    """Record the headers of every call the client makes."""
    calls: list[tuple[str, dict]] = []
    status = {"code": 200}

    def post(url, **kw):
        calls.append(("post", kw.get("headers")))
        return _Resp(status["code"], {"message": {"content": "{}"}})

    def stream(method, url, **kw):
        calls.append(("stream", kw.get("headers")))
        return _Resp(status["code"], lines=[json.dumps({"message": {"content": "hi"}})])

    def get(url, **kw):
        calls.append(("get", kw.get("headers")))
        return _Resp(status["code"], {"models": [{"name": "llama3.1:8b"}]})

    monkeypatch.setattr(httpx, "post", post)
    monkeypatch.setattr(httpx, "stream", stream)
    monkeypatch.setattr(httpx, "get", get)
    return calls, status


def test_client_sends_the_key_on_every_kind_of_call(seen):
    calls, _ = seen
    client = OllamaClient("https://gw.example.org", 5, KEY)
    client._post("/api/chat", {})
    assert list(client._stream("/api/chat", {})) == [{"message": {"content": "hi"}}]
    assert client.status() == {"reachable": True, "models": ["llama3.1:8b"]}
    assert [c[0] for c in calls] == ["post", "stream", "get"]
    assert all(headers == {"Authorization": f"Bearer {KEY}"} for _, headers in calls)


def test_client_without_a_key_sends_no_authorization_header(seen):
    calls, _ = seen
    client = OllamaClient("http://localhost:11434", 5)
    client._post("/api/chat", {})
    list(client._stream("/api/chat", {}))
    client.status()
    assert all(headers == {} for _, headers in calls)


@pytest.mark.parametrize("code", [401, 403])
def test_a_rejected_key_gives_a_clear_message_that_never_echoes_the_key_or_body(seen, code):
    _, status = seen
    status["code"] = code
    client = OllamaClient("https://gw.example.org", 5, KEY)
    with pytest.raises(ServiceUnavailable) as post_err:
        client._post("/api/chat", {})
    with pytest.raises(ServiceUnavailable) as stream_err:
        list(client._stream("/api/chat", {}))
    for err in (post_err.value, stream_err.value):
        assert err.message == REJECTED and KEY not in err.message and "secret body" not in err.message
    assert client.status() == {"reachable": False, "models": []}


@pytest.mark.parametrize("code,message", [(402, PAYMENT), (429, RATE_LIMITED)])
def test_payment_and_rate_limit_errors_say_what_happened(seen, code, message):
    _, status = seen
    status["code"] = code
    client = OllamaClient("https://ollama.com", 5, KEY)
    with pytest.raises(ServiceUnavailable) as err:
        list(client._stream("/api/chat", {}))
    assert err.value.message == message


def test_other_http_errors_keep_the_model_hint(seen):
    _, status = seen
    status["code"] = 404
    with pytest.raises(ServiceUnavailable, match="Is the model pulled"):
        OllamaClient("https://gw.example.org", 5, KEY)._post("/api/chat", {})


def _prod(**kw):
    base = dict(environment="production", jwt_secret="s" * 40, dev_admin_password="", ollama_api_key=KEY)
    return Settings(**{**base, **kw})


def test_production_refuses_to_send_the_key_over_plain_http_to_a_remote_host():
    with pytest.raises(RuntimeError, match="unencrypted"):
        _prod(ollama_base_url="http://ollama.example.org:11434").validate_for_production()
    for ok in ("https://ollama.example.org", "http://localhost:11434", "http://host.docker.internal:11434"):
        _prod(ollama_base_url=ok).validate_for_production()
    _prod(ollama_base_url="http://ollama.example.org:11434", ollama_api_key="").validate_for_production()


# ---------------------------------------------------------------- the gateway

def _upstream(status: int, content: bytes, content_type: str = "application/json") -> httpx.Response:
    """An unread streaming response, like a real server's (a pre-loaded one cannot be streamed again)."""
    return httpx.Response(status, headers={"content-type": content_type}, stream=httpx.ByteStream(content))


def _gateway(handler=None, **kw):
    calls: list[httpx.Request] = []

    def default(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/api/chat":
            return _upstream(200, b'{"message":{"content":"a"}}\n{"done":true}\n', "application/x-ndjson")
        return _upstream(200, b'{"models":[{"name":"llama3.1:8b"}]}')

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler or default), base_url="http://ollama.test")
    return TestClient(gateway.create_app(KEY, client=client, **kw)), calls


AUTH = {"Authorization": f"Bearer {KEY}"}


def test_gateway_rejects_a_missing_or_wrong_key_before_anything_else():
    client, calls = _gateway()
    assert client.get("/api/tags").status_code == 401
    assert client.get("/api/tags", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/tags", headers={"Authorization": KEY}).status_code == 401  # not the Bearer scheme
    assert client.post("/api/pull", headers={"Authorization": "Bearer nope"}).status_code == 401  # no route hints
    assert calls == []


def test_gateway_forwards_only_the_calls_the_application_makes():
    client, calls = _gateway()
    for method, path in [("POST", "/api/pull"), ("DELETE", "/api/delete"), ("POST", "/api/create"),
                         ("POST", "/api/generate"), ("GET", "/api/ps"), ("GET", "/"), ("GET", "/api/chat")]:
        r = client.request(method, path, headers=AUTH)
        assert r.status_code == 404, (method, path)
    assert calls == []  # nothing reached Ollama
    assert client.get("/api/tags", headers=AUTH).json()["models"][0]["name"] == "llama3.1:8b"
    assert client.post("/api/embed", headers=AUTH, json={"model": "m", "input": ["x"]}).status_code == 200
    assert [c.url.path for c in calls] == ["/api/tags", "/api/embed"]


def test_gateway_streams_a_chat_answer_through_unchanged():
    client, calls = _gateway()
    body = {"model": "llama3.1:8b", "stream": True, "messages": [{"role": "user", "content": "hi"}]}
    r = client.post("/api/chat", headers={**AUTH, "content-type": "application/json"}, json=body)
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/x-ndjson")
    assert [json.loads(line) for line in r.text.splitlines()] == [{"message": {"content": "a"}}, {"done": True}]
    assert json.loads(calls[0].content) == body
    assert "authorization" not in calls[0].headers  # the caller's key is not passed on to Ollama
    assert calls[0].headers["accept-encoding"] == "identity"


def test_gateway_passes_ollama_errors_on_and_reports_an_unreachable_ollama():
    client, _ = _gateway(lambda request: _upstream(404, b'{"error":"model not found"}'))
    assert client.post("/api/chat", headers=AUTH, json={}).status_code == 404

    def down(request):
        raise httpx.ConnectError("refused")

    client, _ = _gateway(down)
    r = client.post("/api/chat", headers=AUTH, json={})
    assert r.status_code == 502 and r.json() == {"error": "Ollama is not reachable"}


def test_gateway_limits_request_rate_and_size():
    client, calls = _gateway(per_minute=3)
    assert [client.get("/api/tags", headers=AUTH).status_code for _ in range(4)] == [200, 200, 200, 429]
    assert len(calls) == 3
    client, calls = _gateway()
    too_big = b"x" * (gateway.MAX_BODY_BYTES + 1)
    assert client.post("/api/chat", headers=AUTH, content=too_big).status_code == 413
    assert calls == []


def test_gateway_refuses_a_short_key_and_hides_its_docs():
    with pytest.raises(ValueError, match="at least 32"):
        gateway.create_app("short")
    client, _ = _gateway()
    assert client.get("/docs", headers=AUTH).status_code == 404
    assert client.get("/openapi.json", headers=AUTH).status_code == 404


# ---------------------------------------------------------------- the check-llm command

class _StubClient:
    def __init__(self, models):
        self.models = models

    def status(self):
        return {"reachable": bool(self.models is not None), "models": self.models or []}


class _StubLLM:
    def __init__(self, pieces=None, error=None):
        self.pieces, self.error = pieces, error

    def chat_json_stream(self, system, user):
        if self.error:
            raise self.error
        yield from self.pieces


def _check(monkeypatch, *, models, llm, list_models=False, model="gemma4:12b"):
    import argparse

    from app import cli
    from app.core.config import get_settings
    from app.services import embedding_service

    monkeypatch.setattr(get_settings(), "ollama_llm_model", model)
    monkeypatch.setattr(get_settings(), "ollama_api_key", KEY)
    monkeypatch.setattr(embedding_service, "get_ollama_client", lambda: _StubClient(models))
    monkeypatch.setattr(embedding_service, "get_llm", lambda: llm)
    cli.cmd_check_llm(argparse.Namespace(list=list_models))


def test_check_llm_reports_a_working_setup_without_printing_the_key(monkeypatch, capsys):
    llm = _StubLLM(['{"supported": true,', ' "answer": "Hello there friend"}'])
    _check(monkeypatch, models=["gemma4:12b", "other:1b"], llm=llm, list_models=True)
    out = capsys.readouterr().out
    assert "API key        : set" in out and KEY not in out
    assert "Models listed  : 2" in out and "  other:1b" in out
    assert "Valid JSON     : yes" in out and "OK: this setup can run the assistant." in out


@pytest.mark.parametrize("models,llm,expect", [
    (None, _StubLLM([]), "unreachable, or the API key was rejected"),
    (["other:1b"], _StubLLM([]), "is not in the list"),
    (["gemma4:12b"], _StubLLM(error=ServiceUnavailable("Ollama is not reachable.")), "The model call failed"),
    (["gemma4:12b"], _StubLLM([""]), "returned no text"),
    (["gemma4:12b"], _StubLLM(["not json at all"]), "not valid JSON"),
])
def test_check_llm_explains_each_way_a_setup_can_fail(monkeypatch, capsys, models, llm, expect):
    with pytest.raises(SystemExit) as exc:
        _check(monkeypatch, models=models, llm=llm)
    assert expect in str(exc.value)
    assert KEY not in capsys.readouterr().out + str(exc.value)
