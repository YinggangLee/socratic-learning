import re
from pathlib import Path
from config import TEACHER_DIR, TEACHER_NAMES, TEACHER_DISPLAY


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _md_to_html(md: str) -> str:
    """Simple markdown → HTML converter for panel content."""
    html = md
    # Escape HTML
    html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # But preserve existing <span> tags (teacher expression format)
    html = html.replace('&lt;span style="color: #999;"&gt;', '<span style="color: #999;">')
    html = html.replace("&lt;/span&gt;", '</span>')
    # Inner thought notation: *(text)* → styled span
    html = re.sub(r'\*\((.+?)\)\*', r'<span class="inner-thought">（\1）</span>', html)
    # Code blocks (must be before other transformations)
    html = re.sub(r'```(\w*)\n(.*?)```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)
    # Tables: detect |---|---| pattern, convert surrounding rows
    html = _convert_tables(html)
    # Headings
    html = re.sub(r'^### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    # Italic (single-word emphasis only, not inner thought patterns)
    html = re.sub(r'(?<![<\w])\*(\w+)\*(?![<\w])', r'<em>\1</em>', html)
    # Inline code
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
    # Horizontal rules
    html = re.sub(r'^---+$', '<hr>', html, flags=re.MULTILINE)
    # Blockquotes
    html = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
    # List items
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    # Wrap consecutive <li> in <ul>
    html = re.sub(r'(<li>.*?</li>)\n?(?=<li>|$)', r'\1', html)
    html = html.replace('</li>\n<li>', '</li><li>')
    # Line breaks
    html = html.replace('\n\n', '<br><br>')
    return html


def _convert_tables(html: str) -> str:
    """Convert markdown tables to HTML tables."""
    lines = html.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Check if current + next lines form a table (header | separator | rows)
        if _is_table_row(line) and i + 1 < len(lines) and _is_table_separator(lines[i + 1]):
            # Collect header + all data rows
            table_lines = [line]
            i += 1  # skip separator
            # Collect data rows
            j = i + 1
            while j < len(lines) and _is_table_row(lines[j]):
                table_lines.append(lines[j])
                j += 1
            # Build HTML table
            table_html = _build_table(table_lines)
            result.append(table_html)
            i = j
        else:
            result.append(line)
            i += 1
    return '\n'.join(result)


def _is_table_row(line: str) -> bool:
    """Check if a line looks like a markdown table row."""
    stripped = line.strip()
    return stripped.startswith('|') and stripped.endswith('|') and '|' in stripped[1:-1]


def _is_table_separator(line: str) -> bool:
    """Check if a line is a markdown table separator (e.g. |---|---|)."""
    stripped = line.strip()
    if not (stripped.startswith('|') and stripped.endswith('|')):
        return False
    inner = stripped[1:-1]
    parts = inner.split('|')
    return all(re.match(r'^:?-{2,}:?$', p.strip()) for p in parts if p.strip())


def _build_table(rows: list[str]) -> str:
    """Build an HTML table from markdown table rows."""
    if not rows:
        return ''
    html_rows = []
    for idx, row in enumerate(rows):
        cells = [c.strip() for c in row.strip()[1:-1].split('|')]
        tag = 'th' if idx == 0 else 'td'
        cells_html = ''.join(f'<{tag}>{c}</{tag}>' for c in cells)
        html_rows.append(f'<tr>{cells_html}</tr>')
    return f'<table>{"".join(html_rows)}</table>'


def render_wechat() -> str:
    """Render wechat group chat context."""
    group = _read(TEACHER_DIR / "wechat_group.md")
    unread = _read(TEACHER_DIR / "wechat_unread.md")
    content = f"## 最近群聊\n\n{_summarize(unread, 3000)}\n\n## 历史记录\n\n{_summarize(group, 3000)}"
    return _md_to_html(content)


def render_progress() -> str:
    """Render current learning progress."""
    progress_dir = TEACHER_DIR / "progress"
    if progress_dir.exists():
        for f in progress_dir.iterdir():
            if f.suffix == ".md":
                return _md_to_html(_read(f))
    return "<p>暂无进度记录</p>"


def render_diary() -> str:
    """Render student diary entries."""
    content = _read(TEACHER_DIR / "diary.md")
    if not content:
        return "<p>暂无日记</p>"
    return _md_to_html(_summarize(content, 5000))


def render_teachers() -> str:
    """Render teacher profile summaries."""
    parts = []
    for name in TEACHER_NAMES:
        persona = _read(TEACHER_DIR / f"{name}.md")
        if not persona:
            continue
        # Extract key sections: basic info, personality, teaching style
        display = TEACHER_DISPLAY.get(name, name)
        summary = _extract_summary(persona)
        parts.append(f"## {display}\n\n{summary}")
    return _md_to_html("\n\n---\n\n".join(parts))


def render_toc() -> str:
    """Render textbook table of contents."""
    from config import TEXTBOOK_PATH
    text = _read(TEXTBOOK_PATH)
    if not text:
        return "<p>教材未找到</p>"
    # Extract headings as TOC
    headings = re.findall(r'^(#{1,3})\s+(.+)$', text, re.MULTILINE)
    if not headings:
        return _md_to_html(f"## 教材目录\n\n{text[:2000]}...")
    toc = "## 教材目录\n\n"
    for level, title in headings:
        indent = "  " * (len(level) - 1)
        toc += f"- {indent}**{title.strip()}**\n"
    return _md_to_html(toc)


def _extract_summary(persona: str) -> str:
    """Extract a brief summary from a teacher persona file."""
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


def _summarize(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return "…(earlier content omitted)…\n\n" + text[-max_chars:]


def get_panel_html(name: str, cache: dict[str, str] | None = None) -> str:
    """Get rendered HTML for a panel, with optional caching."""
    if cache and name in cache:
        return cache[name]
    renderers = {
        "wechat": render_wechat,
        "progress": render_progress,
        "diary": render_diary,
        "teachers": render_teachers,
        "toc": render_toc,
    }
    renderer = renderers.get(name)
    if renderer is None:
        return f"<p>未知面板: {name}</p>"
    html = renderer()
    if cache is not None:
        cache[name] = html
    return html


def clear_panel_cache(session):
    """Clear panel cache (called when lesson ends)."""
    if session and hasattr(session, 'panel_cache'):
        session.panel_cache.clear()


def archive_unread_to_group(session) -> dict:
    """Move wechat_unread content to wechat_group, then clear unread."""
    from datetime import datetime
    unread_path = TEACHER_DIR / "wechat_unread.md"
    group_path = TEACHER_DIR / "wechat_group.md"

    if not unread_path.exists() or not unread_path.read_text(encoding="utf-8").strip():
        return {"success": True, "archived": False, "message": "没有未读消息"}

    unread_text = unread_path.read_text(encoding="utf-8").strip()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Append to group
    group_content = _read(group_path)
    entry = f"\n\n---\n## {timestamp} 已读\n\n{unread_text}\n"
    group_path.write_text((group_content + entry).strip(), encoding="utf-8")

    # Clear unread
    unread_path.write_text("（暂无新消息）\n", encoding="utf-8")

    # Clear cache so next panel fetch gets updated content
    if session and hasattr(session, 'panel_cache'):
        session.panel_cache.pop("wechat", None)

    return {"success": True, "archived": True}
