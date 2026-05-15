from typing import Protocol


class PanelRenderer(Protocol):
    def render(self, name: str) -> str: ...

    # Returns HTML for panel name: wechat, progress, diary, teachers, toc


class PanelQueryService(Protocol):
    def get_panel_html(self, name: str) -> str: ...

    def archive_wechat_unread(self) -> dict: ...
