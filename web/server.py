import os
import json
import uuid
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse

from anthropic import AsyncAnthropic

from config import check_config, WEB_DIR, ANTHROPIC_BASE_URL, ANTHROPIC_MODEL, MAX_TOKENS_RESPONSE
from logging_config import setup_logging
from models import ChatRequest, StartResponse, LessonStateResponse, EndResponse, ProgressResponse
from prompt_builder import build_start_prompt, build_chat_messages
from state import get_active_session, create_session, clear_session
from panels import get_panel_html
from post_lesson import run_post_lesson_pipeline
from error_handler import api_call_with_retry

logger = setup_logging()

client = AsyncAnthropic(
    base_url=ANTHROPIC_BASE_URL,
    api_key=os.getenv("ANTHROPIC_API_KEY"),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("启动配置检查...")
    check_config()
    logger.info("配置检查通过")
    yield
    logger.info("服务关闭")


app = FastAPI(title="苏格拉底·七 Web 家教系统", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── /api/lesson/state ──

@app.get("/api/lesson/state")
async def get_lesson_state():
    session = get_active_session()
    if session is None:
        from prompt_builder import _determine_teacher, _get_active_progress
        progress_file, _ = _get_active_progress()
        progress_text = ""
        if progress_file and progress_file.exists():
            progress_text = progress_file.read_text(encoding="utf-8")
        next_teacher_en = _determine_teacher(progress_text) if progress_text else "march7"
        from config import TEACHER_DISPLAY
        return {
            "status": "no_active_lesson",
            "next_teacher": TEACHER_DISPLAY.get(next_teacher_en, "三月七"),
        }
    return {
        "status": "active",
        "teacher_name": session.teacher_name,
        "teacher_display": session.teacher_display,
        "lesson_started_at": session.lesson_started_at,
        "messages": [m.model_dump() for m in session.messages],
    }


# ── /api/lesson/start ──

@app.post("/api/lesson/start")
async def start_lesson():
    existing = get_active_session()
    if existing is not None:
        return {"conflict": True}

    teacher_name, teacher_display, system_prompt = build_start_prompt()
    logger.info(f"开始新课，授课老师: {teacher_display}")

    try:
        response = await api_call_with_retry(
            client.messages.create,
            model=ANTHROPIC_MODEL,
            max_tokens=MAX_TOKENS_RESPONSE,
            system=system_prompt,
            messages=[{"role": "user", "content": "请开始上课。"}],
            thinking={"type": "disabled"},
        )
    except Exception as e:
        logger.error(f"生成开场白失败: {e}")
        return {"error": f"生成开场白失败: {e}"}

    text_blocks = [b for b in response.content if b.type == "text"]
    opening_message = text_blocks[0].text if text_blocks else "（老师暂时没有想好怎么开场……）"
    session = create_session(teacher_name, teacher_display)
    session.add_message("assistant", opening_message)

    return StartResponse(
        teacher_name=teacher_name,
        teacher_display=teacher_display,
        opening_message=opening_message,
    )


# ── /api/lesson/chat ──

@app.post("/api/lesson/chat")
async def chat(req: ChatRequest):
    session = get_active_session()
    if session is None:
        return {"error": "没有活跃课程，请先开始上课"}

    session.add_message("user", req.message)

    # Calculate remaining time
    elapsed = time.time() - session.lesson_started_at
    remaining = max(0, 50 * 60 - elapsed)
    remaining_minutes = int(remaining / 60) if remaining < 600 else None

    system_prompt, api_messages = build_chat_messages(
        teacher_name=session.teacher_name,
        messages=[m.model_dump() for m in session.messages],
        remaining_minutes=remaining_minutes,
    )

    async def event_stream():
        full_text = ""
        try:
            async with client.messages.stream(
                model=ANTHROPIC_MODEL,
                max_tokens=MAX_TOKENS_RESPONSE,
                system=system_prompt,
                messages=api_messages,
                thinking={"type": "disabled"},
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_delta":
                        if event.delta.type == "text_delta":
                            token = event.delta.text
                            full_text += token
                            yield f"data: {json.dumps({'type': 'token', 'text': token}, ensure_ascii=False)}\n\n"
                        # skip thinking_delta — internal reasoning not shown to student
                    elif event.type == "message_stop":
                        pass

            session.add_message("assistant", full_text)
            yield f"data: {json.dumps({'type': 'done', 'full_text': full_text}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"Chat SSE 错误: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── /api/lesson/end ──

@app.post("/api/lesson/end")
async def end_lesson():
    session = get_active_session()
    if session is None:
        return {"error": "没有活跃课程"}

    if session.get_end_job_status() is not None and session.get_end_job_status()["status"] == "processing":
        return {"conflict": True, "existing_job_id": session.get_end_job_status()["job_id"]}

    job_id = uuid.uuid4().hex[:12]
    session.start_end_job(job_id)

    # Phase 7 will implement the actual post-lesson pipeline here
    # For now, simulate a quick completion
    import asyncio
    asyncio.create_task(_run_post_lesson(session, job_id))

    return EndResponse(job_id=job_id, status="processing")


async def _run_post_lesson(session, job_id: str):
    try:
        from pathlib import Path
        from config import TEACHER_DIR

        logger.info(f"课后更新开始: job_id={job_id}")

        # Determine active progress file
        progress_dir = TEACHER_DIR / "progress"
        progress_file = None
        if progress_dir.exists():
            for f in progress_dir.iterdir():
                if f.suffix == ".md":
                    progress_file = f
                    break

        result = await run_post_lesson_pipeline(
            session=session,
            anthropic_client=client,
            progress_file=progress_file,
            teacher_name=session.teacher_name,
            teacher_display=session.teacher_display,
        )
        if result["success"]:
            session.update_end_job(status="done", updated_files=result["updated_files"])
            logger.info(f"课后更新完成: {result['updated_files']}")
            clear_session()
        else:
            session.update_end_job(status="failed", error=result.get("error"))
            logger.error(f"课后更新失败: {result.get('error')}")
    except Exception as e:
        logger.error(f"课后更新异常: {e}")
        session.update_end_job(status="failed", error=str(e))


# ── /api/lesson/end/progress/{job_id} ──

@app.get("/api/lesson/end/progress/{job_id}")
async def get_end_progress(job_id: str):
    session = get_active_session()
    if session is None:
        return ProgressResponse(status="failed", error="没有活跃课程")

    status = session.get_end_job_status()
    if status is None:
        return ProgressResponse(status="failed", error="未找到该任务")

    return ProgressResponse(
        status=status["status"],
        updated_files=status.get("updated_files"),
        error=status.get("error"),
    )


# ── /api/panels/{name} ──

@app.get("/api/panels/{name}")
async def get_panel(name: str):
    session = get_active_session()
    cache = session.panel_cache if session else None
    html = get_panel_html(name, cache)
    return {"name": name, "html": html}


# ── /api/panels/wechat/archive ──

@app.post("/api/panels/wechat/archive")
async def archive_wechat():
    session = get_active_session()
    try:
        from panels import archive_unread_to_group
        result = archive_unread_to_group(session)
        return result
    except Exception as e:
        logger.error(f"归档微信未读失败: {e}")
        return {"success": False, "error": str(e)}


# ── 静态文件 ──

app.mount("/", StaticFiles(directory=str(WEB_DIR / "static"), html=True), name="static")


def main():
    logger.info("启动服务 http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
