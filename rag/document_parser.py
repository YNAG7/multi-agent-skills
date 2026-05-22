from __future__ import annotations

import re
from importlib import import_module
from collections import Counter
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader


PARSER_VERSION = "document-parser-v1"
CLEANING_VERSION = "cleaning-v1"
MIN_TEXT_LENGTH = 8


def _detect_encoding(raw: bytes) -> str:
    try:
        from charset_normalizer import from_bytes

        best = from_bytes(raw).best()
        if best and best.encoding:
            return best.encoding
    except Exception:
        pass

    for encoding in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue

    return "utf-8"


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("\u3000", " ")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _merge_broken_lines(text: str) -> str:
    lines = [line.strip() for line in _normalize_newlines(text).split("\n")]
    merged: list[str] = []

    for line in lines:
        if not line:
            if merged and merged[-1] != "":
                merged.append("")
            continue

        if not merged or merged[-1] == "":
            merged.append(line)
            continue

        previous = merged[-1]
        if previous.endswith("-") and line and line[0].islower():
            merged[-1] = previous[:-1] + line
            continue

        if _should_join_line(previous, line):
            merged[-1] = f"{previous} {line}"
            continue

        merged.append(line)

    return "\n".join(merged)


def _should_join_line(previous: str, current: str) -> bool:
    if not previous or not current:
        return False
    if previous.endswith((".", "?", "!", "。", "？", "！", ":", "：", ";", "；")):
        return False
    if _looks_like_heading(previous) or _looks_like_heading(current):
        return False
    if re.match(r"^[-*•]\s+", current):
        return False
    if re.match(r"^\d+[.)、]\s+", current):
        return False
    return True


def _looks_like_heading(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    if len(text) > 80:
        return False
    if re.match(r"^(#{1,6}\s+|第[一二三四五六七八九十百千万\d]+[章节篇]|[一二三四五六七八九十]+[、.])", text):
        return True
    if re.match(r"^(标题|章节?|小节|附录)\s*[\w\u4e00-\u9fff-]*$", text):
        return True
    if re.match(r"^\d+(\.\d+){0,4}\s+\S+", text):
        return True
    return text.isupper() and len(text.split()) <= 10


def _is_noise_line(line: str) -> bool:
    text = line.strip()
    if not text:
        return False
    if re.fullmatch(r"[-_=*·•]{3,}", text):
        return True
    if re.fullmatch(r"(page\s*)?\d+\s*(/\s*\d+)?", text, flags=re.IGNORECASE):
        return True
    if len(text) < 3 and not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", text):
        return True
    return False


def _remove_repeated_headers_footers(page_texts: list[str]) -> list[str]:
    if len(page_texts) < 3:
        return page_texts

    candidates: Counter[str] = Counter()
    for page_text in page_texts:
        lines = [line.strip() for line in _normalize_newlines(page_text).split("\n") if line.strip()]
        for line in lines[:2] + lines[-2:]:
            if 3 <= len(line) <= 120:
                candidates[line] += 1

    repeated = {
        line
        for line, count in candidates.items()
        if count >= max(3, int(len(page_texts) * 0.5))
    }
    if not repeated:
        return page_texts

    cleaned: list[str] = []
    for page_text in page_texts:
        lines = [
            line
            for line in _normalize_newlines(page_text).split("\n")
            if line.strip() not in repeated
        ]
        cleaned.append("\n".join(lines))

    return cleaned


def clean_text(text: str) -> str:
    text = _merge_broken_lines(text)
    lines = [
        line
        for line in text.split("\n")
        if not _is_noise_line(line)
    ]
    return _normalize_whitespace("\n".join(lines))


def _sectionize(document: Document) -> list[Document]:
    text = document.page_content
    if not text:
        return []

    sections: list[tuple[str | None, list[str]]] = []
    current_title: str | None = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()
        if _looks_like_heading(stripped):
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = stripped.lstrip("#").strip()
            current_lines = [stripped]
            continue

        current_lines.append(line)

    if current_lines:
        sections.append((current_title, current_lines))

    result: list[Document] = []
    for index, (title, lines) in enumerate(sections):
        content = clean_text("\n\n".join(lines) if title else "\n".join(lines))
        if len(content) < MIN_TEXT_LENGTH:
            continue

        metadata = {
            **document.metadata,
            "section_index": index,
            "section_title": title,
        }
        result.append(Document(page_content=content, metadata=metadata))

    return result


def parse_txt(path: Path) -> list[Document]:
    raw = path.read_bytes()
    encoding = _detect_encoding(raw)
    text = raw.decode(encoding, errors="replace")
    text = clean_text(text)
    if len(text) < MIN_TEXT_LENGTH:
        return []

    document = Document(
        page_content=text,
        metadata={
            "source": str(path),
            "file_type": "txt",
            "encoding": encoding,
            "parser": "text",
            "parser_version": PARSER_VERSION,
            "cleaning_version": CLEANING_VERSION,
        },
    )
    return _sectionize(document)


def parse_pdf(path: Path) -> list[Document]:
    pages, parser_name = _extract_pdf_pages(path)
    pages = _remove_repeated_headers_footers(pages)

    documents: list[Document] = []
    for index, page_text in enumerate(pages):
        text = clean_text(page_text)
        if len(text) < MIN_TEXT_LENGTH:
            continue

        page_document = Document(
            page_content=text,
            metadata={
                "source": str(path),
                "file_type": "pdf",
                "page": index + 1,
                "parser": parser_name,
                "parser_version": PARSER_VERSION,
                "cleaning_version": CLEANING_VERSION,
            },
        )
        documents.extend(_sectionize(page_document))

    return documents


def _extract_pdf_pages(path: Path) -> tuple[list[str], str]:
    try:
        fitz = import_module("fitz")
        with fitz.open(str(path)) as pdf:
            return [page.get_text("text") for page in pdf], "pymupdf"
    except Exception:
        pass

    try:
        pdfium = import_module("pypdfium2")
        pdf = pdfium.PdfDocument(str(path))
        pages: list[str] = []
        try:
            for index in range(len(pdf)):
                page = pdf[index]
                textpage = page.get_textpage()
                pages.append(textpage.get_text_range())
        finally:
            pdf.close()
        return pages, "pypdfium2"
    except Exception:
        pass

    documents = PyPDFLoader(str(path)).load()
    pages_by_number: dict[int, str] = {}
    fallback_pages: list[str] = []
    for document in documents:
        page = document.metadata.get("page")
        if isinstance(page, int):
            pages_by_number[page + 1] = document.page_content
        else:
            fallback_pages.append(document.page_content)

    if pages_by_number:
        return [pages_by_number[key] for key in sorted(pages_by_number)], "pypdf"
    return fallback_pages, "pypdf"


def parse_document(path: str | Path) -> list[Document]:
    file_path = Path(path).resolve()
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(file_path)
    if suffix == ".txt":
        return parse_txt(file_path)
    return []
