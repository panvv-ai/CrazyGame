from __future__ import annotations

import json
import queue
import threading
import uuid

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select

from src.crazygame.core.timeutils import iso_utc
from src.crazygame.domain.models import AIReport, AppSetting, Instrument
from src.crazygame.services.ai import resolve_runtime_ai_client
from src.crazygame.services.ai_agent import AIAgentRunner
from src.crazygame.services.ai_chat import AIChatService, instrument_payload
from src.crazygame.services.ai_report import (
    AIReportCancelled,
    AIReportGenerationError,
    AIReportService,
)

router = APIRouter()


class ChatPayload(BaseModel):
    message: str
    session_id: str | None = None
    instrument_id: int | None = None


class ReportPayload(BaseModel):
    instrument_id: int


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _resolve_ai(request: Request):
    config = request.app.state.config
    return resolve_runtime_ai_client(
        session_factory=request.app.state.session_factory,
        secret_box=request.app.state.secret_box,
        fallback_base_url=config.ai_base_url,
        fallback_api_key=config.ai_api_key,
        fallback_model=config.ai_model,
        fallback_vision_model=config.ai_vision_model,
        runtime_client=request.app.state.ai,
    )


def _news_enabled(request: Request) -> bool:
    with request.app.state.session_factory() as db:
        row = db.get(AppSetting, "news")
        if row is None:
            return request.app.state.config.news_enabled
        try:
            payload = json.loads(row.value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return request.app.state.config.news_enabled
        return bool(payload.get("enabled", True))


def _language(request: Request) -> str:
    with request.app.state.session_factory() as db:
        row = db.get(AppSetting, "language")
        return row.value if row is not None and row.value else "zh-CN"


def report_dict(row: AIReport) -> dict:
    try:
        report = json.loads(row.report_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        report = {}
    return {
        "id": row.id,
        "instrument": instrument_payload(row.instrument),
        "status": row.status,
        "language": row.language,
        "title": row.title,
        "verdict": row.verdict,
        "confidence": row.confidence,
        "score": row.score,
        "content_markdown": row.content_markdown,
        "report": report,
        "model_label": row.model_label,
        "error": row.error,
        "created_at": iso_utc(row.created_at),
    }


@router.post("/chat/stream")
def chat_stream(payload: ChatPayload, request: Request):
    chat_service = AIChatService(request.app.state.session_factory)
    try:
        turn = chat_service.prepare_turn(
            message=payload.message,
            session_id=payload.session_id,
            instrument_id=payload.instrument_id,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    def event_stream():
        language = _language(request)
        accepted = {
            "type": "accepted",
            "request_id": turn.request_id,
            "session_id": turn.session_id,
            "active_instrument": instrument_payload(turn.instrument),
        }
        yield _sse(accepted)
        if turn.instrument is None:
            message = "请明确提供股票代码，或从搜索结果中选择一个标的。"
            chat_service.save_assistant(turn.session_id, message)
            yield _sse(
                {
                    "type": "clarification",
                    "request_id": turn.request_id,
                    "session_id": turn.session_id,
                    "message": message,
                    "candidates": turn.candidates,
                }
            )
            return
        ai = _resolve_ai(request)
        if ai is None:
            yield _sse(
                {
                    "type": "error",
                    "request_id": turn.request_id,
                    "code": "ai_not_configured",
                    "message": "请先在设置中配置 AI 服务。",
                    "session_id": turn.session_id,
                }
            )
            return
        events: queue.Queue = queue.Queue()
        cancelled = threading.Event()

        def worker():
            try:
                events.put(
                    {
                        "type": "stage",
                        "request_id": turn.request_id,
                        "session_id": turn.session_id,
                        "stage": "context",
                    }
                )
                def progress(event):
                    event.update(
                        {
                            "request_id": turn.request_id,
                            "session_id": turn.session_id,
                        }
                    )
                    events.put(event)

                context = request.app.state.ai_context_service.build(
                    turn.instrument,
                    language=language,
                    include_news=_news_enabled(request),
                )
                runner = AIAgentRunner(
                    ai_client=ai,
                    context=context,
                    language=language,
                )
                prepared, tool_log = runner.prepare(
                    turn.message,
                    history=turn.history,
                    progress_callback=progress,
                )
                events.put(
                    {
                        "type": "stage",
                        "request_id": turn.request_id,
                        "session_id": turn.session_id,
                        "stage": "compose",
                    }
                )
                chunks = []
                for chunk in runner.stream_answer(prepared):
                    chunks.append(chunk)
                    events.put(
                        {
                            "type": "delta",
                            "request_id": turn.request_id,
                            "session_id": turn.session_id,
                            "content": chunk,
                        }
                    )
                content = "".join(chunks).strip()
                if not content:
                    raise ValueError("AI returned an empty answer")
                if cancelled.is_set():
                    return
                chat_service.save_assistant(
                    turn.session_id,
                    content,
                    tools=tool_log,
                )
                events.put(
                    {
                        "type": "done",
                        "request_id": turn.request_id,
                        "session_id": turn.session_id,
                        "content": content,
                    }
                )
            except Exception as exc:
                events.put(
                    {
                        "type": "error",
                        "request_id": turn.request_id,
                        "code": "ai_chat_failed",
                        "message": str(exc)[:300],
                        "session_id": turn.session_id,
                    }
                )
            finally:
                events.put(None)

        threading.Thread(target=worker, daemon=True).start()
        try:
            while True:
                event = events.get()
                if event is None:
                    break
                yield _sse(event)
        finally:
            cancelled.set()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/chat/sessions")
def list_chat_sessions(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
):
    return {
        "items": AIChatService(request.app.state.session_factory).list_sessions(limit)
    }


@router.get("/chat/sessions/{session_id}")
def get_chat_session(session_id: str, request: Request):
    session = AIChatService(request.app.state.session_factory).get_session(session_id)
    if session is None:
        raise HTTPException(404, "chat session not found")
    return session


@router.delete("/chat/sessions/{session_id}")
def delete_chat_session(session_id: str, request: Request):
    deleted = AIChatService(request.app.state.session_factory).delete_session(
        session_id
    )
    if not deleted:
        raise HTTPException(404, "chat session not found")
    return {"ok": True}


@router.post("/reports/stream")
def report_stream(payload: ReportPayload, request: Request):
    with request.app.state.session_factory() as db:
        instrument = db.get(Instrument, payload.instrument_id)
    if instrument is None:
        raise HTTPException(404, "instrument not found")
    if instrument.asset_type == "open_end_fund":
        raise HTTPException(422, "open-end funds are not supported")

    def event_stream():
        request_id = uuid.uuid4().hex
        yield _sse(
            {
                "type": "accepted",
                "request_id": request_id,
                "instrument": instrument_payload(instrument),
            }
        )
        ai = _resolve_ai(request)
        if ai is None:
            yield _sse(
                {
                    "type": "error",
                    "request_id": request_id,
                    "code": "ai_not_configured",
                    "message": "请先在设置中配置 AI 服务。",
                }
            )
            return
        events: queue.Queue = queue.Queue()
        cancelled = threading.Event()

        def worker():
            try:
                service = AIReportService(
                    session_factory=request.app.state.session_factory,
                    context_service=request.app.state.ai_context_service,
                    ai_client=ai,
                )
                result = service.generate(
                    instrument,
                    language=_language(request),
                    include_news=_news_enabled(request),
                    progress_callback=lambda stage: events.put(
                        {
                            "type": "stage",
                            "request_id": request_id,
                            "stage": stage,
                        }
                    ),
                    is_cancelled=cancelled.is_set,
                )
                if cancelled.is_set():
                    return
                events.put({"type": "done", "request_id": request_id, **result})
            except AIReportCancelled:
                return
            except AIReportGenerationError as exc:
                events.put(
                    {
                        "type": "error",
                        "request_id": request_id,
                        "code": "report_generation_failed",
                        "message": str(exc),
                    }
                )
            except Exception as exc:
                events.put(
                    {
                        "type": "error",
                        "request_id": request_id,
                        "code": "report_generation_failed",
                        "message": str(exc)[:300],
                    }
                )
            finally:
                events.put(None)

        threading.Thread(target=worker, daemon=True).start()
        try:
            while True:
                event = events.get()
                if event is None:
                    break
                yield _sse(event)
        finally:
            cancelled.set()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/reports")
def list_reports(
    request: Request,
    instrument_id: int | None = None,
    limit: int = Query(default=30, ge=1, le=100),
):
    with request.app.state.session_factory() as db:
        query = select(AIReport).order_by(
            AIReport.created_at.desc(), AIReport.id.desc()
        )
        if instrument_id is not None:
            query = query.where(AIReport.instrument_id == instrument_id)
        rows = db.scalars(query.limit(limit)).all()
        return {"items": [report_dict(row) for row in rows]}


@router.get("/reports/{report_id}")
def get_report(report_id: int, request: Request):
    with request.app.state.session_factory() as db:
        row = db.get(AIReport, report_id)
        if row is None:
            raise HTTPException(404, "AI report not found")
        return report_dict(row)


@router.delete("/reports/{report_id}")
def delete_report(report_id: int, request: Request):
    with request.app.state.session_factory() as db:
        row = db.get(AIReport, report_id)
        if row is None:
            raise HTTPException(404, "AI report not found")
        db.delete(row)
        db.commit()
    return {"ok": True}
