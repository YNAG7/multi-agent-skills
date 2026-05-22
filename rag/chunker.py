from __future__ import annotations

import re
from dataclasses import dataclass

from langchain_core.documents import Document


CHUNKING_VERSION = "parent-child-v1"


@dataclass
class ChildChunk:
    text: str
    metadata: dict


@dataclass
class ParentChunk:
    text: str
    metadata: dict
    children: list[ChildChunk]

# 将一个大块切分成多个小块，同时保留父子关系和必要的上下文信息。
def build_parent_child_chunks(
    documents: list[Document],
    parent_size: int = 1200,
    parent_overlap: int = 120,
    child_size: int = 360,
    child_overlap: int = 80,
) -> list[ParentChunk]:
    parents: list[ParentChunk] = []

    for source_index, document in enumerate(documents):
        # 父块切分
        parent_texts = _split_text(
            document.page_content,
            max_size=parent_size,
            overlap=parent_overlap,
        )

        for parent_text in parent_texts:
            parent_index = len(parents)
            parent_metadata = {
                **(document.metadata or {}),
                "chunk_type": "parent",
                "parent_index": parent_index,
                "source_section_index": source_index,
                "chunking_version": CHUNKING_VERSION,
            }
            
            # 子块切分
            children: list[ChildChunk] = []
            child_texts = _split_text(
                parent_text,
                max_size=child_size,
                overlap=child_overlap,
            )
            for child_index, child_text in enumerate(child_texts):
                children.append(
                    ChildChunk(
                        text=child_text,
                        metadata={
                            **parent_metadata,
                            "chunk_type": "child",
                            "child_index": child_index,
                        },
                    )
                )

            if children:
                parents.append(
                    ParentChunk(
                        text=parent_text,
                        metadata=parent_metadata,
                        children=children,
                    )
                )

    return parents


def _split_text(text: str, max_size: int, overlap: int) -> list[str]:
    # 文本预处理与规范化
    text = _normalize_text(text)
    if not text:
        return []
    if len(text) <= max_size:
        return [text]
    
    # 分块
    # 粗分
    units = _semantic_units(text, max_size)
    # 细分
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for unit in units:
        unit_len = len(unit)
        separator_len = 2 if current else 0
        if current and current_len + separator_len + unit_len > max_size:
            chunks.append("\n\n".join(current).strip())
            current = [unit]
            current_len = unit_len
        else:
            current.append(unit)
            current_len += separator_len + unit_len

    if current:
        chunks.append("\n\n".join(current).strip())

    return _add_overlap(chunks, overlap)


def _normalize_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _semantic_units(text: str, max_size: int) -> list[str]:
    paragraphs = [
        item.strip()
        for item in re.split(r"\n{2,}", text)
        if item.strip()
    ]

    if len(paragraphs) <= 1:
        paragraphs = _split_sentences(text)

    units: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= max_size:
            units.append(paragraph)
            continue

        sentences = _split_sentences(paragraph)
        if len(sentences) <= 1:
            units.extend(_hard_split(paragraph, max_size))
            continue

        units.extend(_pack_small_units(sentences, max_size))

    return units


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []

    parts = re.split(r"(?<=[。！？.!?；;])\s*", normalized)
    return [part.strip() for part in parts if part.strip()]


def _pack_small_units(units: list[str], max_size: int) -> list[str]:
    chunks: list[str] = []
    current = ""

    for unit in units:
        if not current:
            current = unit
            continue

        candidate = f"{current} {unit}"
        if len(candidate) <= max_size:
            current = candidate
        else:
            chunks.append(current)
            current = unit

    if current:
        if len(current) <= max_size:
            chunks.append(current)
        else:
            chunks.extend(_hard_split(current, max_size))

    return chunks


def _hard_split(text: str, max_size: int) -> list[str]:
    return [
        text[start:start + max_size].strip()
        for start in range(0, len(text), max_size)
        if text[start:start + max_size].strip()
    ]


def _add_overlap(chunks: list[str], overlap: int) -> list[str]:
    if overlap <= 0 or len(chunks) <= 1:
        return chunks

    result = [chunks[0]]
    for index in range(1, len(chunks)):
        prefix = _tail_text(chunks[index - 1], overlap)
        chunk = chunks[index]
        result.append(f"{prefix}\n\n{chunk}".strip() if prefix else chunk)

    return result


def _tail_text(text: str, length: int) -> str:
    text = text.strip()
    if len(text) <= length:
        return text

    tail = text[-length:]
    paragraph_break = tail.find("\n\n")
    if paragraph_break >= 0 and paragraph_break + 2 < len(tail):
        return tail[paragraph_break + 2:].strip()

    sentence_breaks = [
        tail.rfind(mark)
        for mark in ("。", "！", "？", ".", "!", "?")
    ]
    sentence_break = max(sentence_breaks)
    if sentence_break >= 0 and sentence_break + 1 < len(tail):
        return tail[sentence_break + 1:].strip()

    return tail.strip()
