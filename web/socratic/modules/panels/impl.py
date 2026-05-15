"""Panel rendering implementation."""

from pathlib import Path
import re


class MarkdownPanelRenderer:
    def render_wechat(self, group_text: str, unread_text: str) -> str:
        content = f"## 最近群聊\n\n{unread_text[:3000] if unread_text else ''}\n\n## 历史记录\n\n{group_text[:3000] if group_text else ''}"
        return self._md_to_html(content)

    def render_progress(self, progress_text: str) -> str:
        if progress_text:
            return self._md_to_html(progress_text)
        return "<p>暂无进度记录</p>"

    def render_diary(self, diary_text: str) -> str:
        if not diary_text:
            return "<p>暂无日记</p>"
        text = diary_text if len(diary_text) <= 5000 else "…(earlier content omitted)…\n\n" + diary_text[-5000:]
        return self._md_to_html(text)

    def render_teachers(self, teacher_infos: list[dict]) -> str:
        parts = []
        for info in teacher_infos:
            display = info.get("display", info["name"])
            persona = info.get("persona", "")
            summary = self._extract_summary(persona) if persona else "暂无资料"
            parts.append(f"## {display}\n\n{summary}")
        return self._md_to_html("\n\n---\n\n".join(parts))

    def render_toc(self, textbook_text: str) -> str:
        if not textbook_text:
            return "<p>教材未找到</p>"
        headings = re.findall(r"^(#{1,3})\s+(.+)$", textbook_text, re.MULTILINE)
        if not headings:
            return self._md_to_html(f"## 教材目录\n\n{textbook_text[:2000]}...")
        toc = "## 教材目录\n\n"
        for level, title in headings:
            indent = "  " * (len(level) - 1)
            toc += f"- {indent}**{title.strip()}**\n"
        return self._md_to_html(toc)

    def _md_to_html(self, md: str) -> str:
        html = md
        html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = html.replace('&lt;span style="color: #999;"&gt;', '<span style="color: #999;">')
        html = html.replace("&lt;/span&gt;", "</span>")
        html = re.sub(r"\*\((.+?)\)\*", r'<span class="inner-thought">（\1）</span>', html)
        html = re.sub(r"```(\w*)\n(.*?)```", r"<pre><code>\2</code></pre>", html, flags=re.DOTALL)
        html = self._convert_tables(html)
        html = re.sub(r"^### (.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"(?<![<\w])\*(\w+)\*(?![<\w])", r"<em>\1</em>", html)
        html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)
        html = re.sub(r"^---+$", "<hr>", html, flags=re.MULTILINE)
        html = re.sub(r"^&gt; (.+)$", r"<blockquote>\1</blockquote>", html, flags=re.MULTILINE)
        html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
        html = html.replace("</li>\n<li>", "</li><li>")
        html = html.replace("\n\n", "<br><br>")
        return html

    def _convert_tables(self, html: str) -> str:
        lines = html.split("\n")
        result = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if self._is_table_row(line) and i + 1 < len(lines) and self._is_table_separator(lines[i + 1]):
                table_lines = [line]
                i += 1
                j = i + 1
                while j < len(lines) and self._is_table_row(lines[j]):
                    table_lines.append(lines[j])
                    j += 1
                result.append(self._build_table(table_lines))
                i = j
            else:
                result.append(line)
                i += 1
        return "\n".join(result)

    def _is_table_row(self, line: str) -> bool:
        s = line.strip()
        return s.startswith("|") and s.endswith("|") and "|" in s[1:-1]

    def _is_table_separator(self, line: str) -> bool:
        s = line.strip()
        if not (s.startswith("|") and s.endswith("|")):
            return False
        inner = s[1:-1]
        parts = inner.split("|")
        return all(re.match(r"^:?-{2,}:?$", p.strip()) for p in parts if p.strip())

    def _build_table(self, rows: list[str]) -> str:
        html_rows = []
        for idx, row in enumerate(rows):
            cells = [c.strip() for c in row.strip()[1:-1].split("|")]
            tag = "th" if idx == 0 else "td"
            cells_html = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
            html_rows.append(f"<tr>{cells_html}</tr>")
        return f"<table>{''.join(html_rows)}</table>"

    def _extract_summary(self, persona: str) -> str:
        lines = persona.split("\n")
        wanted = []
        in_section = False
        for line in lines:
            if line.startswith("## ") and "小动作" not in line:
                in_section = True
            if line.startswith("## 小动作"):
                in_section = False
            if line.startswith("## 家庭"):
                break
            if line.startswith("## 人生"):
                break
            if in_section:
                wanted.append(line)
        return "\n".join(wanted)


class CachedPanelService:
    def __init__(
        self,
        renderer: MarkdownPanelRenderer,
        teacher_repo,  # TeacherProfileRepository
        textbook_catalog,  # TextbookCatalog
        storage,  # FileStorage
        teacher_dir: Path,
        teacher_names: list[str],
        teacher_display: dict[str, str],
        get_progress_text,  # callable → str (resolved lazily)
        get_active_textbook_path,  # callable → str (resolved lazily)
    ):
        self._renderer = renderer
        self._teachers = teacher_repo
        self._catalog = textbook_catalog
        self._storage = storage
        self._teacher_dir = teacher_dir
        self._names = teacher_names
        self._display = teacher_display
        self._get_progress = get_progress_text
        self._get_textbook = get_active_textbook_path
        self._cache: dict[str, str] = {}

    def get_panel_html(self, name: str) -> str:
        if name in self._cache:
            return self._cache[name]
        html = self._render(name)
        self._cache[name] = html
        return html

    def invalidate_cache(self):
        self._cache.clear()

    def archive_wechat_unread(self) -> dict:
        from datetime import datetime

        unread_path = self._teacher_dir / "wechat_unread.md"
        group_path = self._teacher_dir / "wechat_group.md"

        if not unread_path.exists() or not unread_path.read_text(encoding="utf-8").strip():
            return {"success": True, "archived": False, "message": "没有未读消息"}

        unread_text = unread_path.read_text(encoding="utf-8").strip()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        group_content = self._storage.read_text(group_path)
        entry = f"\n\n---\n## {timestamp} 已读\n\n{unread_text}\n"
        self._storage.write_text(group_path, (group_content + entry).strip())
        unread_path.write_text("（暂无新消息）\n", encoding="utf-8")
        self._cache.pop("wechat", None)
        return {"success": True, "archived": True}

    def _render(self, name: str) -> str:
        if name == "wechat":
            group = self._storage.read_text(self._teacher_dir / "wechat_group.md")
            unread = self._storage.read_text(self._teacher_dir / "wechat_unread.md")
            return self._renderer.render_wechat(group, unread)
        elif name == "progress":
            return self._renderer.render_progress(self._get_progress())
        elif name == "diary":
            return self._renderer.render_diary(self._storage.read_text(self._teacher_dir / "diary.md"))
        elif name == "teachers":
            infos = []
            for n in self._names:
                infos.append(
                    {
                        "name": n,
                        "display": self._display.get(n, n),
                        "persona": self._teachers.get_persona(n),
                    }
                )
            return self._renderer.render_teachers(infos)
        elif name == "toc":
            return self._renderer.render_toc(self._storage.read_text(self._get_textbook()))
        return f"<p>未知面板: {name}</p>"
