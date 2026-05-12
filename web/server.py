import os
import json
import uuid
import time
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request, UploadFile, File, Form
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
    # Treat session with terminal end_job as ended
    if session is not None:
        job = session.get_end_job_status()
        if job and job["status"] in ("done", "failed"):
            session = None
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
        job = existing.get_end_job_status()
        if job and job["status"] in ("done", "failed"):
            clear_session()
        else:
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
        from prompt_builder import _get_active_progress

        logger.info(f"课后更新开始: job_id={job_id}")

        progress_file, _ = _get_active_progress()

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


# ── /api/lesson/clear ──

@app.post("/api/lesson/clear")
async def clear_lesson():
    clear_session()
    return {"success": True}


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


# ── /api/textbooks ──

from textbook_store import get_store
from textbook_models import TextbookCreateRequest, TextbookStatusRequest, TextbookStatus, ImportStatus
from textbook_importer import (
    slugify_name, create_textbook_dirs, import_markdown_file,
    save_uploaded_pdf, extract_pdf_text, pdf_to_markdown, url_to_markdown,
)


@app.get("/api/textbooks")
async def list_textbooks(show_deleted: bool = False):
    store = get_store()
    records = store.list_all(show_deleted=show_deleted)
    return {
        "textbooks": [r.model_dump() for r in records],
        "active_id": store.get_active_id(),
    }


@app.get("/api/textbooks/{textbook_id}")
async def get_textbook(textbook_id: str):
    store = get_store()
    record = store.get(textbook_id)
    if record is None:
        return {"error": "教材未找到"}
    return record.model_dump()


@app.post("/api/textbooks")
async def create_textbook(
    name: str = Form(...),
    source_type: str = Form(...),
    source_ref: str = Form(None),
    set_active: bool = Form(False),
    file: UploadFile | None = File(None),
    url: str = Form(None),
):
    store = get_store()
    from config import BASE_DIR

    content_path, progress_path = create_textbook_dirs(name, BASE_DIR)

    if source_type == "file_md" and file:
        import tempfile, shutil
        src = content_path.parent / f"_tmp_{file.filename}"
        with open(src, "wb") as f:
            f.write(await file.read())
        success = import_markdown_file(src, content_path)
        src.unlink(missing_ok=True)
        if not success:
            content_path.unlink(missing_ok=True)
            return {"error": "文件为空或无效"}
        record = store.add(
            name=name, source_type=source_type, source_ref=source_ref or file.filename,
            content_path=str(content_path.relative_to(BASE_DIR)),
            progress_path=str(progress_path.relative_to(BASE_DIR)),
            import_status=ImportStatus.ready,
        )
    elif source_type == "file_pdf" and file:
        from config import TEXTBOOK_DIR
        original_dir = TEXTBOOK_DIR / "originals"
        pdf_bytes = await file.read()
        original_path = save_uploaded_pdf(pdf_bytes, original_dir, file.filename or "upload.pdf")
        record = store.add(
            name=name, source_type=source_type, source_ref=source_ref or file.filename,
            content_path=str(content_path.relative_to(BASE_DIR)),
            progress_path=str(progress_path.relative_to(BASE_DIR)),
            original_path=str(original_path.relative_to(BASE_DIR)),
            import_status=ImportStatus.processing,
        )
        # Start background import
        import asyncio
        asyncio.create_task(_run_pdf_import(record.id, original_path, content_path, name))
    elif source_type == "url":
        if not url:
            return {"error": "URL 导入需要提供 url 参数"}
        record = store.add(
            name=name, source_type=source_type, source_ref=url,
            content_path=str(content_path.relative_to(BASE_DIR)),
            progress_path=str(progress_path.relative_to(BASE_DIR)),
            import_status=ImportStatus.processing,
        )
        import asyncio
        asyncio.create_task(_run_url_import(record.id, url, content_path, name))
    else:
        return {"error": f"不支持的来源类型: {source_type}"}

    if set_active and record.import_status == ImportStatus.ready:
        store.set_active(record.id)
        record = store.get(record.id)
    return record.model_dump()


async def _run_pdf_import(textbook_id: str, original_path: Path, content_path: Path, name: str):
    store = get_store()
    from config import BASE_DIR
    abs_original = BASE_DIR / original_path
    abs_content = BASE_DIR / content_path
    text = extract_pdf_text(abs_original)
    if not text:
        store.set_import_error(textbook_id, "PDF 文本提取失败")
        return
    markdown = await pdf_to_markdown(text, name, client)
    if not markdown:
        store.set_import_error(textbook_id, "LLM 转换 Markdown 失败")
        return
    abs_content.write_text(markdown, encoding="utf-8")
    store.set_import_ready(textbook_id)
    logger.info(f"PDF 导入完成: {textbook_id}")


async def _run_url_import(textbook_id: str, url: str, content_path: Path, name: str):
    store = get_store()
    from config import BASE_DIR
    abs_content = BASE_DIR / content_path
    markdown, error = await url_to_markdown(url, name, client)
    if error or not markdown:
        store.set_import_error(textbook_id, error or "导入失败")
        return
    abs_content.write_text(markdown, encoding="utf-8")
    store.set_import_ready(textbook_id)
    logger.info(f"URL 导入完成: {textbook_id}")


@app.put("/api/textbooks/{textbook_id}/status")
async def update_textbook_status(textbook_id: str, req: TextbookStatusRequest):
    store = get_store()
    record = store.get(textbook_id)
    if record is None:
        return {"error": "教材未找到"}
    try:
        if req.status == TextbookStatus.active:
            store.set_active(textbook_id)
        elif req.status == TextbookStatus.completed:
            store.mark_completed(textbook_id)
        elif req.status == TextbookStatus.deleted:
            store.soft_delete(textbook_id)
        else:
            store._update_status(textbook_id, req.status)
        return store.get(textbook_id).model_dump()
    except ValueError as e:
        return {"error": str(e)}


@app.post("/api/textbooks/{textbook_id}/restore")
async def restore_textbook(textbook_id: str):
    store = get_store()
    record = store.get(textbook_id)
    if record is None:
        return {"error": "教材未找到"}
    try:
        store.restore(textbook_id)
        return store.get(textbook_id).model_dump()
    except ValueError as e:
        return {"error": str(e)}


@app.post("/api/textbooks/{textbook_id}/retry-import")
async def retry_import(textbook_id: str):
    store = get_store()
    record = store.get(textbook_id)
    if record is None:
        return {"error": "教材未找到"}
    from config import BASE_DIR
    if record.source_type == "url":
        store.set_import_processing(textbook_id)
        import asyncio
        asyncio.create_task(_run_url_import(
            textbook_id, record.source_ref,
            Path(record.content_path), record.name))
    elif record.source_type == "file_pdf" and record.original_path:
        store.set_import_processing(textbook_id)
        import asyncio
        asyncio.create_task(_run_pdf_import(
            textbook_id, record.original_path,
            Path(record.content_path), record.name))
    else:
        return {"error": "此教材类型不支持重试导入"}
    return {"status": "processing"}


@app.get("/api/textbooks/registry.md")
async def get_registry_md():
    from config import TEXTBOOK_DIR
    md_path = TEXTBOOK_DIR / "textbook_registry.md"
    if md_path.exists():
        return {"markdown": md_path.read_text(encoding="utf-8")}
    return {"markdown": ""}


# ── 静态文件 ──

app.mount("/", StaticFiles(directory=str(WEB_DIR / "static"), html=True), name="static")


def main():
    logger.info("启动服务 http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
