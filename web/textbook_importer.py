import re
from pathlib import Path


def slugify_name(name: str) -> str:
    raw = name.lower().strip()
    raw = re.sub(r'[^a-z0-9\s-]', '', raw)
    raw = re.sub(r'\s+', '-', raw)
    return raw.strip('-') or "untitled"


def create_textbook_dirs(name: str, base_dir: Path) -> tuple[Path, Path]:
    """Create content_path and progress_path for a new textbook.
    Returns (content_path, progress_path)."""
    tid = slugify_name(name)
    content_path = base_dir / "textbook" / "imported" / f"{tid}.md"
    progress_path = base_dir / "teacher" / "progress" / f"{tid}.md"
    content_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    return content_path, progress_path


def import_markdown_file(source_path: Path, content_path: Path) -> bool:
    """Copy a markdown file to the textbook content path.
    Returns True on success, False on empty/invalid source."""
    text = source_path.read_text(encoding="utf-8").strip()
    if not text:
        return False
    content_path.write_text(text, encoding="utf-8")
    if not content_path.exists() or content_path.stat().st_size == 0:
        return False
    return True


def save_uploaded_pdf(source_bytes: bytes, original_dir: Path, filename: str) -> Path:
    """Save uploaded PDF to textbook/originals/. Returns original_path."""
    original_dir.mkdir(parents=True, exist_ok=True)
    dest = original_dir / filename
    dest.write_bytes(source_bytes)
    return dest


def extract_pdf_text(pdf_path: Path) -> str | None:
    """Extract raw text from a PDF using PyMuPDF. Returns None on failure."""
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text.strip() or None
    except Exception:
        return None


async def pdf_to_markdown(pdf_text: str, name: str, anthropic_client) -> str | None:
    """Convert extracted PDF text to Markdown via LLM."""
    prompt = f"""将以下从 PDF 提取的文本整理成结构清晰的 Markdown 教材。
教材名称：{name}

要求：
- 保留原文的章节结构，用 # ## ### 表示层级
- 保留关键概念、定义、示例
- 去除页眉页脚、页码等噪音
- 代码块用 ``` 包裹
- 表格用 Markdown 表格格式

原始文本：
{pdf_text[:80000]}"""

    try:
        response = await anthropic_client.messages.create(
            model="deepseek-v4-pro[1m]",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "disabled"},
        )
        text_blocks = [b for b in response.content if b.type == "text"]
        if text_blocks:
            return text_blocks[0].text
        return None
    except Exception:
        return None


async def url_to_markdown(url: str, name: str, anthropic_client) -> tuple[str | None, str | None]:
    """Fetch URL content, convert to Markdown via LLM.
    Returns (markdown, error_message)."""
    try:
        import httpx
        from bs4 import BeautifulSoup

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            body = soup.find("body")
            text = body.get_text("\n", strip=True) if body else soup.get_text("\n", strip=True)
            if not text or len(text) < 100:
                return None, "抓取的内容过短，可能不是文章页面"

            prompt = f"""将以下网页内容整理成结构清晰的 Markdown 教材。
教材名称：{name}
来源 URL：{url}

要求：
- 保留原文的章节结构，用 # ## ### 表示层级
- 保留关键概念、定义、示例
- 代码块用 ``` 包裹
- 表格用 Markdown 表格格式

原始内容：
{text[:80000]}"""

            response = await anthropic_client.messages.create(
                model="deepseek-v4-pro[1m]",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
                thinking={"type": "disabled"},
            )
            text_blocks = [b for b in response.content if b.type == "text"]
            if text_blocks:
                return text_blocks[0].text, None
            return None, "LLM 返回空内容"
    except Exception as e:
        return None, str(e)
