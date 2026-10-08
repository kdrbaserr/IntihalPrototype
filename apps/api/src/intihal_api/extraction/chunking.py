from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

PARAGRAPH_PATTERN = re.compile(r"[^\n\s](?:[^\n]*[^\n\s])?")
SENTENCE_END_PATTERN = re.compile(r"[.!?…]+(?=\s|$)")
TOKEN_PATTERN = re.compile(r"\b\w+\b", re.UNICODE)

TURKISH_ABBREVIATIONS = frozenset(
    {
        "bkz.",
        "doç.",
        "dr.",
        "hz.",
        "no.",
        "örn.",
        "prof.",
        "s.",
        "sf.",
        "sn.",
        "vb.",
        "vd.",
        "vs.",
        "yrd.",
    }
)


class ExtractedTextPart(Protocol):
    """The common fields exposed by PDF pages and DOCX/TXT extraction results."""

    @property
    def text(self) -> str: ...

    @property
    def page_number(self) -> int | None: ...


@dataclass(frozen=True, slots=True)
class TextChunk:
    """A sentence-sized piece whose offsets point into ``ChunkedText.text``."""

    chunk_index: int
    content: str
    char_start: int
    char_end: int
    token_count: int
    page_number: int | None
    content_sha256: str


@dataclass(frozen=True, slots=True)
class ChunkedText:
    """Canonical document text together with traceable paragraph/sentence chunks."""

    text: str
    chunks: tuple[TextChunk, ...]


def create_text_chunks(parts: Iterable[ExtractedTextPart]) -> ChunkedText:
    """Create non-overlapping chunks without allowing one chunk to cross a page."""

    extracted_parts = tuple(parts)
    document_text = "\n".join(part.text for part in extracted_parts)
    chunks: list[TextChunk] = []
    part_start = 0

    for part in extracted_parts:
        for local_start, local_end in _sentence_spans(part.text):
            content = part.text[local_start:local_end]
            chunks.append(
                TextChunk(
                    chunk_index=len(chunks),
                    content=content,
                    char_start=part_start + local_start,
                    char_end=part_start + local_end,
                    token_count=len(TOKEN_PATTERN.findall(content)),
                    page_number=part.page_number,
                    content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                )
            )
        part_start += len(part.text) + 1

    return ChunkedText(text=document_text, chunks=tuple(chunks))


def _sentence_spans(text: str) -> Iterable[tuple[int, int]]:
    for paragraph_match in PARAGRAPH_PATTERN.finditer(text):
        paragraph_start, paragraph_end = paragraph_match.span()
        sentence_start = paragraph_start

        for ending_match in SENTENCE_END_PATTERN.finditer(text, paragraph_start, paragraph_end):
            if _is_abbreviation(text, sentence_start, ending_match.end()):
                continue
            yield _trimmed_span(text, sentence_start, ending_match.end())
            sentence_start = ending_match.end()

        if sentence_start < paragraph_end:
            yield _trimmed_span(text, sentence_start, paragraph_end)


def _is_abbreviation(text: str, sentence_start: int, ending: int) -> bool:
    if text[ending - 1] != ".":
        return False

    word_start = ending - 1
    while word_start > sentence_start and not text[word_start - 1].isspace():
        word_start -= 1
    candidate = text[word_start:ending].casefold()
    return candidate in TURKISH_ABBREVIATIONS or (len(candidate) == 2 and candidate[0].isalpha())


def _trimmed_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end
