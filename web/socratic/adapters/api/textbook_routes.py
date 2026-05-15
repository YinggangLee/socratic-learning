"""Textbook API routes — thin adapter, delegates to application services."""

from fastapi import APIRouter, File, Form, Request, UploadFile

from .dependencies import get_textbook_service
from .schemas import TextbookStatusRequest

router = APIRouter(prefix="/api/textbooks", tags=["textbooks"])
SUPPORTED_SOURCE_TYPES = {"file_md", "file_pdf", "url"}


@router.get("")
async def list_textbooks(request: Request, show_deleted: bool = False):
    svc = get_textbook_service(request)
    return svc.list_textbooks(show_deleted=show_deleted)


@router.get("/registry.md")
async def get_registry_md(request: Request):
    svc = get_textbook_service(request)
    return svc.get_registry_md()


@router.get("/{textbook_id}")
async def get_textbook(textbook_id: str, request: Request):
    svc = get_textbook_service(request)
    return svc.get_textbook(textbook_id)


@router.post("")
async def create_textbook(
    request: Request,
    name: str = Form(...),
    source_type: str = Form(...),
    source_ref: str = Form(None),
    set_active: bool = Form(False),
    file: UploadFile | None = File(None),
    url: str = Form(None),
):
    svc = get_textbook_service(request)
    if source_type not in SUPPORTED_SOURCE_TYPES:
        return {"error": f"不支持的来源类型: {source_type}"}
    if source_type in {"file_md", "file_pdf"} and file is None:
        return {"error": "文件上传需要提供 file 参数"}
    if source_type == "url" and not url:
        return {"error": "URL 导入需要提供 url 参数"}

    result = svc.create_textbook(name=name, source_type=source_type, source_ref=source_ref, set_active=set_active)
    if "error" in result:
        return result

    textbook_id = result["id"]

    if source_type == "file_md" and file:
        content = await file.read()
        filename = file.filename or "upload.md"
        result = svc.import_file_md(textbook_id, content, filename, source_ref)
    elif source_type == "file_pdf" and file:
        content = await file.read()
        filename = file.filename or "upload.pdf"
        result = svc.import_file_pdf(textbook_id, content, filename)
    elif source_type == "url":
        result = svc.import_url(textbook_id, url)

    return result


@router.put("/{textbook_id}/status")
async def update_textbook_status(textbook_id: str, req: TextbookStatusRequest, request: Request):
    svc = get_textbook_service(request)
    return svc.update_status(textbook_id, req.status)


@router.post("/{textbook_id}/restore")
async def restore_textbook(textbook_id: str, request: Request):
    svc = get_textbook_service(request)
    return svc.restore(textbook_id)


@router.post("/{textbook_id}/retry-import")
async def retry_import(textbook_id: str, request: Request):
    svc = get_textbook_service(request)
    return svc.retry_import(textbook_id)
