import json
import logging
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.errors import AppError, NotFound
from app.core.ratelimit import rate_limit
from app.db.session import SessionLocal, get_db
from app.models import ChatMessage, Conversation, Role, User, _now
from app.schemas import ChatIn, ChatOut, ConversationDetail, ConversationOut, FeedbackIn, MessageOut
from app.services import audit_service, rag_service

log = logging.getLogger("infomind.chat")
router = APIRouter(tags=["assistant"])
analyst = require_roles(Role.analyst)


def _owned(db: Session, user: User, conversation_id: str) -> Conversation:
    """Conversations are strictly private to their owner, admins included (404 hides existence)."""
    conv = db.get(Conversation, conversation_id)
    if conv is None or conv.owner_id != user.id:
        raise NotFound("Conversation not found")
    return conv


def _save_exchange(db: Session, user: User, conv: Conversation | None, question: str, result: rag_service.RagResult,
                   start: float, request: Request) -> ChatOut:
    if conv is None:
        conv = Conversation(owner_id=user.id, title=question[:80])
        db.add(conv)
        db.flush()
    db.add(ChatMessage(conversation_id=conv.id, role="user", content=question))
    msg = ChatMessage(conversation_id=conv.id, role="assistant", content=result.answer, citations=result.citations,
                      sufficient_evidence=result.sufficient_evidence,
                      latency_ms=int((time.monotonic() - start) * 1000))
    db.add(msg)
    conv.updated_at = _now()
    db.commit()
    audit_service.record(db, action="assistant.ask", actor_id=user.id, target_type="conversation", target_id=conv.id,
                         request=request, detail=f"sufficient={result.sufficient_evidence}")
    return ChatOut(conversation_id=conv.id, message=MessageOut.model_validate(msg),
                   retrieval_mode=result.retrieval_mode, excluded_suspicious=result.excluded_suspicious,
                   inference=result.inference)


@router.post("/chat", response_model=ChatOut, dependencies=[rate_limit("chat", 12)])
def chat(body: ChatIn, request: Request, user: User = Depends(analyst), db: Session = Depends(get_db)):
    conv = _owned(db, user, body.conversation_id) if body.conversation_id else None
    start = time.monotonic()
    result = rag_service.answer_question(db, user, body.question)  # raises 503 if the LLM is unavailable
    return _save_exchange(db, user, conv, body.question, result, start, request)


def _sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat/stream", dependencies=[rate_limit("chat", 12)])
def chat_stream(body: ChatIn, request: Request, user: User = Depends(analyst), db: Session = Depends(get_db)):
    """Same answer as POST /chat, delivered as Server-Sent Events: meta, citations, delta*, then done (or error).
    `delta` text is provisional and only sent after the citations were validated; `done` carries the stored message
    and is authoritative. Nothing is saved if the client disconnects before `done`."""
    if body.conversation_id:
        _owned(db, user, body.conversation_id)  # 404 before any streaming starts
    user_id, conv_id, question = user.id, body.conversation_id, body.question

    def events():
        start = time.monotonic()
        with SessionLocal() as s:  # own session: the request-scoped one is not guaranteed to outlive the response
            try:
                u = s.get(User, user_id)
                conv = _owned(s, u, conv_id) if conv_id else None
                for kind, payload in rag_service.answer_question_stream(s, u, question):
                    if kind == "final":
                        out = _save_exchange(s, u, conv, question, payload, start, request)
                        yield _sse("done", out.model_dump(mode="json"))
                    elif kind == "citations":
                        yield _sse("citations", payload)
                    elif kind == "delta":
                        yield _sse("delta", {"text": payload})
                    else:
                        yield _sse("meta", payload)
            except AppError as exc:
                yield _sse("error", {"message": exc.message, "status": exc.status_code})
            except Exception:  # noqa: BLE001 - never leak internals into the stream
                log.exception("assistant stream failed")
                yield _sse("error", {"message": "The assistant failed unexpectedly. Please retry.", "status": 500})

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(user: User = Depends(analyst), db: Session = Depends(get_db)):
    return list(db.scalars(select(Conversation).where(Conversation.owner_id == user.id)
                           .order_by(Conversation.updated_at.desc()).limit(100)))


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: str, user: User = Depends(analyst), db: Session = Depends(get_db)):
    return _owned(db, user, conversation_id)


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str, request: Request, user: User = Depends(analyst),
                        db: Session = Depends(get_db)):
    conv = _owned(db, user, conversation_id)
    db.delete(conv)
    db.commit()
    audit_service.record(db, action="conversation.delete", actor_id=user.id, target_type="conversation",
                         target_id=conversation_id, request=request)


@router.post("/messages/{message_id}/feedback", status_code=204)
def feedback(message_id: str, body: FeedbackIn, user: User = Depends(analyst), db: Session = Depends(get_db)):
    msg = db.get(ChatMessage, message_id)
    if msg is None or msg.role != "assistant" or _owned(db, user, msg.conversation_id) is None:
        raise NotFound("Message not found")
    msg.feedback = body.feedback
    db.commit()
