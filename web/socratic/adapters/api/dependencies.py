"""FastAPI dependency injection — get services from app.state.container."""
from fastapi import Request


def get_container(request: Request):
    return request.app.state.container


def get_lesson_service(request: Request):
    return get_container(request).lesson_service


def get_textbook_service(request: Request):
    return get_container(request).textbook_service


def get_panel_service(request: Request):
    return get_container(request).panel_service
