"""Panel application service — panel rendering with caching."""

import logging

logger = logging.getLogger("socratic.application.panel")


class PanelService:
    def __init__(self, panel_query_service):
        self._query = panel_query_service

    def get_panel_html(self, name: str) -> dict:
        html = self._query.get_panel_html(name)
        return {"name": name, "html": html}

    def archive_wechat(self) -> dict:
        return self._query.archive_wechat_unread()

    def invalidate_cache(self):
        self._query.invalidate_cache()
