"""Textbook application service — orchestrates textbook lifecycle."""

import logging
from pathlib import Path
import re

logger = logging.getLogger("socratic.application.textbook")


def _slugify(text: str) -> str:
    raw = text.lower().strip()
    raw = re.sub(r"[^a-z0-9\s-]", "", raw)
    raw = re.sub(r"\s+", "-", raw)
    return raw.strip("-") or "untitled"


class TextbookService:
    def __init__(
        self,
        catalog,  # TextbookCatalog
        llm_client,  # AsyncLLMClient
        job_runner,  # JobRunner
        storage,  # FileStorage
        base_dir: Path,
    ):
        self._catalog = catalog
        self._llm = llm_client
        self._jobs = job_runner
        self._storage = storage
        self._base_dir = base_dir

    # ── List / Get ──

    def list_textbooks(self, show_deleted: bool = False) -> dict:
        records = self._catalog.list_textbooks(show_deleted=show_deleted)
        return {
            "textbooks": [self._record_to_dict(r) for r in records],
            "active_id": self._catalog.get_active_id(),
        }

    def get_textbook(self, textbook_id: str) -> dict:
        record = self._catalog.get_by_id(textbook_id)
        if record is None:
            return {"error": "教材未找到"}
        return self._record_to_dict(record)

    def get_registry_md(self) -> dict:
        md_path = self._base_dir / "textbook" / "textbook_registry.md"
        if md_path.exists():
            return {"markdown": md_path.read_text(encoding="utf-8")}
        return {"markdown": ""}

    # ── Create ──

    def create_textbook(
        self, name: str, source_type: str, source_ref: str | None = None, set_active: bool = False
    ) -> dict:
        from socratic.modules.textbook.models import CreateTextbookCommand

        catalog = self._catalog
        cmd = CreateTextbookCommand(name=name, source_type=source_type, source_ref=source_ref, set_active=set_active)
        record = catalog.create(cmd)

        # Create directories and progress template
        content_path, progress_path = self._create_textbook_dirs(name, override_id=record.id)
        catalog.update_content_path(record.id, str(content_path.relative_to(self._base_dir)))
        catalog.update_progress_path(record.id, str(progress_path.relative_to(self._base_dir)))

        if set_active:
            catalog.mark_pending_activation(record.id)

        return self._record_to_dict(catalog.get_by_id(record.id))

    def import_file_md(self, textbook_id: str, content: bytes, filename: str, source_ref: str | None = None) -> dict:

        catalog = self._catalog
        record = catalog.get_by_id(textbook_id)
        if record is None:
            return {"error": "教材未找到"}

        content_path = self._base_dir / record.content_path
        tmp_src = content_path.parent / f"_tmp_{Path(filename).name}"
        tmp_src.write_bytes(content)
        text = tmp_src.read_text(encoding="utf-8").strip()
        tmp_src.unlink(missing_ok=True)

        if not text:
            content_path.unlink(missing_ok=True)
            catalog.set_import_error(textbook_id, "文件为空或无效")
            return {"error": "文件为空或无效"}

        content_path.write_text(text, encoding="utf-8")
        if not content_path.exists() or content_path.stat().st_size == 0:
            catalog.set_import_error(textbook_id, "写入后验证失败")
            return {"error": "写入后验证失败"}

        if not source_ref:
            source_ref = Path(filename).name
        catalog.update_source_ref(textbook_id, source_ref)
        catalog.set_import_ready(textbook_id)
        return self._record_to_dict(catalog.get_by_id(textbook_id))

    def import_file_pdf(self, textbook_id: str, content: bytes, filename: str) -> dict:
        catalog = self._catalog
        record = catalog.get_by_id(textbook_id)
        if record is None:
            return {"error": "教材未找到"}

        originals_dir = self._base_dir / "textbook" / "originals"
        originals_dir.mkdir(parents=True, exist_ok=True)
        original_path = originals_dir / Path(filename).name
        original_path.write_bytes(content)

        catalog.update_original_path(textbook_id, str(original_path.relative_to(self._base_dir)))
        catalog.update_source_ref(textbook_id, Path(filename).name)
        catalog.set_import_processing(textbook_id)
        self._jobs.run_background(
            self._run_pdf_import, textbook_id, original_path, self._base_dir / record.content_path, record.name
        )
        return self._record_to_dict(catalog.get_by_id(textbook_id))

    def import_url(self, textbook_id: str, url: str) -> dict:
        catalog = self._catalog
        record = catalog.get_by_id(textbook_id)
        if record is None:
            return {"error": "教材未找到"}

        catalog.update_source_ref(textbook_id, url)
        catalog.set_import_processing(textbook_id)
        self._jobs.run_background(
            self._run_url_import, textbook_id, url, self._base_dir / record.content_path, record.name
        )
        return self._record_to_dict(catalog.get_by_id(textbook_id))

    # ── Status Management ──

    def update_status(self, textbook_id: str, status: str) -> dict:
        from socratic.modules.textbook.models import TextbookStatus

        try:
            if status == TextbookStatus.active.value:
                self._catalog.activate(textbook_id)
            elif status == TextbookStatus.completed.value:
                self._catalog.mark_completed(textbook_id)
            elif status == TextbookStatus.deleted.value:
                self._catalog.soft_delete(textbook_id)
            else:
                return {"error": f"不支持的状态: {status}"}
            return self._record_to_dict(self._catalog.get_by_id(textbook_id))
        except Exception as e:
            return {"error": str(e)}

    def restore(self, textbook_id: str) -> dict:
        try:
            self._catalog.restore(textbook_id)
            return self._record_to_dict(self._catalog.get_by_id(textbook_id))
        except Exception as e:
            return {"error": str(e)}

    def retry_import(self, textbook_id: str) -> dict:
        catalog = self._catalog
        record = catalog.get_by_id(textbook_id)
        if record is None:
            return {"error": "教材未找到"}

        if record.source_type == "url":
            if not record.source_ref:
                return {"error": "URL 来源缺失，无法重试导入"}
            catalog.set_import_processing(textbook_id)
            self._jobs.run_background(
                self._run_url_import, textbook_id, record.source_ref, self._base_dir / record.content_path, record.name
            )
        elif record.source_type == "file_pdf" and record.original_path:
            catalog.set_import_processing(textbook_id)
            self._jobs.run_background(
                self._run_pdf_import,
                textbook_id,
                self._base_dir / record.original_path,
                self._base_dir / record.content_path,
                record.name,
            )
        else:
            return {"error": "此教材类型不支持重试导入"}
        return {"status": "processing"}

    # ── Private helpers ──

    def _create_textbook_dirs(self, name: str, override_id: str = "") -> tuple[Path, Path]:
        tid = override_id or _slugify(name)
        content_path = self._base_dir / "textbook" / "imported" / f"{tid}.md"
        progress_path = self._base_dir / "teacher" / "progress" / f"{tid}.md"
        content_path.parent.mkdir(parents=True, exist_ok=True)
        progress_path.parent.mkdir(parents=True, exist_ok=True)
        template = f"# 学习进度 — {name}\n\n| 日期 | 课节 | 授课老师 | 内容 | 掌握情况 |\n|------|------|----------|------|----------|\n\n当前章节：待开始\n\n下一位授课老师：三月七\n"
        progress_path.write_text(template, encoding="utf-8")
        return content_path, progress_path

    async def _run_pdf_import(self, textbook_id: str, original_path: Path, content_path: Path, name: str):
        try:
            # PDF extraction
            try:
                import fitz

                doc = fitz.open(str(original_path))
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
            except Exception:
                self._catalog.set_import_error(textbook_id, "PDF 文本提取失败")
                return

            if not text:
                self._catalog.set_import_error(textbook_id, "PDF 文本提取失败")
                return

            prompt = f"""将以下从 PDF 提取的文本整理成结构清晰的 Markdown 教材。
教材名称：{name}

要求：
- 保留原文的章节结构，用 # ## ### 表示层级
- 保留关键概念、定义、示例
- 去除页眉页脚、页码等噪音
- 代码块用 ``` 包裹
- 表格用 Markdown 表格格式

原始文本：
{text[:80000]}"""

            markdown = await self._llm.create_message(
                system="", messages=[{"role": "user", "content": prompt}], max_tokens=4096
            )
            if not markdown:
                self._catalog.set_import_error(textbook_id, "LLM 转换 Markdown 失败")
                return

            content_path.write_text(markdown, encoding="utf-8")
            self._catalog.set_import_ready(textbook_id)
            logger.info(f"PDF 导入完成: {textbook_id}")
        except Exception as e:
            self._catalog.set_import_error(textbook_id, str(e))

    async def _run_url_import(self, textbook_id: str, url: str, content_path: Path, name: str):
        try:
            from bs4 import BeautifulSoup
            import httpx

            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                body = soup.find("body")
                text = body.get_text("\n", strip=True) if body else soup.get_text("\n", strip=True)
                if not text or len(text) < 100:
                    self._catalog.set_import_error(textbook_id, "抓取的内容过短，可能不是文章页面")
                    return

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

                markdown = await self._llm.create_message(
                    system="", messages=[{"role": "user", "content": prompt}], max_tokens=4096
                )
                if not markdown:
                    self._catalog.set_import_error(textbook_id, "LLM 返回空内容")
                    return

                content_path.write_text(markdown, encoding="utf-8")
                self._catalog.set_import_ready(textbook_id)
                logger.info(f"URL 导入完成: {textbook_id}")
        except Exception as e:
            self._catalog.set_import_error(textbook_id, str(e))

    def _record_to_dict(self, record) -> dict:
        if hasattr(record, "model_dump"):
            return record.model_dump()
        if hasattr(record, "__dict__"):
            d = dict(record.__dict__)
            # Convert enums to strings
            for k, v in d.items():
                if hasattr(v, "value"):
                    d[k] = v.value
            return d
        return dict(record)
