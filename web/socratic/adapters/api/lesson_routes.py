"""Lesson API routes — thin adapter, delegates to application services."""

import json
import logging
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .dependencies import get_container, get_lesson_service
from .schemas import ChatRequest, EndResponse

logger = logging.getLogger("socratic.api.lesson")

router = APIRouter(prefix="/api/lesson", tags=["lesson"])


@router.get("/state")
async def get_state(request: Request):
    svc = get_lesson_service(request)
    return svc.get_state()


@router.post("/start")
async def start_lesson(request: Request):
    svc = get_lesson_service(request)
    return await svc.start_lesson()


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    svc = get_lesson_service(request)
    result = await svc.chat(req.message)
    if "error" in result:
        return result

    system_prompt = result["system_prompt"]
    api_messages = result["api_messages"]

    async def event_stream():
        full_text = ""
        try:
            async for token in svc.get_stream(system_prompt, api_messages):
                if await request.is_disconnected():
                    break
                full_text += token
                yield f"data: {json.dumps({'type': 'token', 'text': token}, ensure_ascii=False)}\n\n"
            if not await request.is_disconnected():
                svc.finalize_chat_message(full_text)
                yield f"data: {json.dumps({'type': 'done', 'full_text': full_text}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            logger.error("Chat SSE 错误: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/end")
async def end_lesson(request: Request):
    svc = get_lesson_service(request)
    container = get_container(request)
    job_id = uuid.uuid4().hex[:12]
    result = svc.end_lesson(job_id)
    if "conflict" in result or "error" in result:
        return result

    container.job_runner.run_background(container.post_lesson_service.run, job_id)
    return EndResponse(job_id=job_id, status="processing")


@router.get("/end/progress/{job_id}")
async def get_end_progress(job_id: str, request: Request):
    svc = get_lesson_service(request)
    return svc.get_end_progress(job_id)


@router.post("/clear")
async def clear_lesson(request: Request):
    svc = get_lesson_service(request)
    svc.clear()
    return {"success": True}
