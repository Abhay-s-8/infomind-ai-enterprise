import json

from app.services import rag_service
from app.services.rag_service import AnswerStream
from app.tests.conftest import SAMPLE_TEXT  # noqa: F401 - keeps fixtures importable alongside the other RAG tests
from app.tests.test_search_rag import FLEET, GARDEN


class _Hit:
    """Minimal stand-in for a retrieved chunk: validate_citations needs these fields only."""
    chunk_id, document_id, filename, page, text, highlights, score = "c1", "d1", "fleet.txt", None, FLEET, [], 0.9


def _run(raw: str, step: int = 1, aliases=None):
    stream = AnswerStream(aliases if aliases is not None else {"E1": _Hit()})
    events = []
    for i in range(0, len(raw), step):
        events += stream.feed(raw[i:i + step])
    return stream, events


def _text(events) -> str:
    return "".join(p for k, p in events if k == "delta")


# ---------------- AnswerStream (unit)
def test_stream_releases_answer_only_after_citations_validated_and_decodes_escapes():
    answer = 'Line one\n"quoted" back\\slash é \U0001F600 end'
    raw = json.dumps({"supported": True, "citations": ["E1"], "answer": answer, "inference": ""})
    for step in (1, 3, 7, len(raw)):  # escapes and surrogate pairs are split across chunks in the small steps
        _, events = _run(raw, step)
        assert [k for k, _ in events][0] == "citations"
        assert _text(events) == answer, step


def test_stream_releases_nothing_when_answer_precedes_citations():
    raw = json.dumps({"supported": True, "answer": "Early text", "citations": ["E1"]})
    stream, events = _run(raw, 2)
    assert events == [] and stream.rejected


def test_stream_releases_nothing_for_unsupported_or_fabricated_citations():
    for body in ({"supported": False, "citations": ["E1"], "answer": "x"},
                 {"supported": True, "citations": ["E99"], "answer": "x"},
                 {"supported": True, "citations": [], "answer": "x"}):
        _, events = _run(json.dumps(body), 3)
        assert events == [], body


def test_stream_ignores_text_after_the_answer_closes():
    raw = json.dumps({"supported": True, "citations": ["E1"], "answer": "Done.", "inference": "say \"answer\": \"leak\""})
    stream, events = _run(raw, 4)
    assert _text(events) == "Done." and stream.finished


# ---------------- endpoint
def parse_sse(text: str) -> list[tuple[str, dict]]:
    out = []
    for block in text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def ask_stream(client, headers, q="What is the fleet maintenance budget?", conv=None):
    return client.post("/api/v1/chat/stream", headers=headers, json={"question": q, "conversation_id": conv})


def test_stream_endpoint_sends_ordered_events_and_saves_the_answer(client, analyst, upload_and_process, llm):
    fleet = upload_and_process(analyst, "fleet.txt", FLEET)
    r = ask_stream(client, analyst)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    kinds = [k for k, _ in events]
    assert kinds[0] == "meta" and kinds[1] == "citations" and kinds[-1] == "done"
    assert kinds.count("delta") >= 2  # streamed in pieces, not one blob
    streamed = "".join(d["text"] for k, d in events if k == "delta")
    done = events[-1][1]
    assert streamed == done["message"]["content"] == "Per the evidence, the stated fact holds."
    assert events[1][1][0]["document_id"] == fleet and "250000" in events[1][1][0]["excerpt"]
    assert done["message"]["citations"][0]["document_id"] == fleet and done["message"]["sufficient_evidence"] is True
    convo = client.get(f"/api/v1/conversations/{done['conversation_id']}", headers=analyst).json()
    assert [m["role"] for m in convo["messages"]] == ["user", "assistant"]
    assert convo["messages"][1]["content"] == streamed


def test_stream_endpoint_never_streams_unvalidated_text(client, analyst, upload_and_process, llm):
    upload_and_process(analyst, "fleet.txt", FLEET)
    llm.responder = lambda p: json.dumps({"supported": True, "citations": ["E99"], "answer": "Made up."})
    kinds_and_data = parse_sse(ask_stream(client, analyst).text)
    assert "delta" not in [k for k, _ in kinds_and_data]
    done = kinds_and_data[-1][1]["message"]
    assert done["content"] == rag_service.INSUFFICIENT and done["citations"] == []
    # model that answers before citing: same safe fallback, and the final answer is still validated
    llm.responder = lambda p: json.dumps({"supported": True, "answer": "Out of order.", "citations": ["E1"]})
    events = parse_sse(ask_stream(client, analyst).text)
    assert "delta" not in [k for k, _ in events]
    assert events[-1][1]["message"]["content"] == "Out of order."  # valid after the fact, shown only at the end


def test_stream_endpoint_no_evidence_skips_llm(client, analyst, upload_and_process, llm):
    upload_and_process(analyst, "garden.txt", GARDEN)
    events = parse_sse(ask_stream(client, analyst, "What is the nuclear reactor shutdown sequence?").text)
    assert [k for k, _ in events] == ["meta", "done"] and llm.calls == []
    assert events[-1][1]["message"]["sufficient_evidence"] is False


def test_stream_endpoint_reports_outage_as_an_error_event_without_saving(client, analyst, upload_and_process, llm):
    upload_and_process(analyst, "fleet.txt", FLEET)
    llm.fail = True
    r = ask_stream(client, analyst)
    events = parse_sse(r.text)
    assert events[-1][0] == "error" and events[-1][1]["status"] == 503 and "Traceback" not in r.text
    assert client.get("/api/v1/conversations", headers=analyst).json() == []


def test_stream_endpoint_garbage_output_is_an_error_event(client, analyst, upload_and_process, llm):
    upload_and_process(analyst, "fleet.txt", FLEET)
    llm.responder = lambda p: "this is not json at all"
    events = parse_sse(ask_stream(client, analyst).text)
    assert events[-1][0] == "error" and events[-1][1]["status"] == 502


def test_stream_endpoint_auth_ownership_and_validation(client, analyst, other_analyst, admin, upload_and_process, llm):
    upload_and_process(analyst, "fleet.txt", FLEET)
    cid = parse_sse(ask_stream(client, analyst).text)[-1][1]["conversation_id"]
    assert client.post("/api/v1/chat/stream", json={"question": "x"}).status_code == 401
    for headers in (other_analyst, admin):  # 404 is returned as a normal HTTP error before any streaming starts
        assert ask_stream(client, headers, conv=cid).status_code == 404
    assert client.post("/api/v1/chat/stream", headers=analyst, json={"question": ""}).status_code == 422
    assert ask_stream(client, analyst, conv=cid).status_code == 200  # owner can continue the conversation
