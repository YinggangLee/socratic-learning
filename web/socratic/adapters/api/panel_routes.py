"""Panel API routes — thin adapter, delegates to panel services."""

import logging

from fastapi import APIRouter, Request

from .dependencies import get_panel_service

logger = logging.getLogger("socratic.api.panels")

router = APIRouter(prefix="/api/panels", tags=["panels"])


@router.get("/{name}")
async def get_panel(name: str, request: Request):
    svc = get_panel_service(request)
    return svc.get_panel_html(name)


@router.post("/wechat/archive")
async def archive_wechat(request: Request):
    svc = get_panel_service(request)
    return svc.archive_wechat()
