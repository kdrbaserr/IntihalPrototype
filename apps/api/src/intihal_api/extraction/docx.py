from __future__ import annotations

from dataclasses import dataclass
from io import SEEK_SET
from typing import BinaryIO
from zipfile import BadZipFile

from docx import Document
from docx.opc.exceptions import OpcError
from docx.table import Table
from docx.text.paragraph import Paragraph
from lxml.etree import XMLSyntaxError

from intihal_api.extraction.normalization import normalize_extracted_text


@dataclass(frozen=True, slots=True)
class ExtractedDocxText:
    """Text extracted from a DOCX whose rendered page number is not knowable."""

    text: str
    page_number: None = None


class DocxExtractionError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class InvalidDocxError(DocxExtractionError):
    def __init__(self) -> None:
        super().__init__("invalid_docx", "DOCX açılamadı veya dosya yapısı bozuk.")


class NoExtractableDocxTextError(DocxExtractionError):
    def __init__(self) -> None:
        super().__init__("no_extractable_text", "DOCX içinde çıkarılabilir metin bulunamadı.")


def extract_docx_text(stream: BinaryIO) -> ExtractedDocxText:
    """Extract body paragraphs and table cells in their document order."""

    stream.seek(0, SEEK_SET)
    try:
        try:
            document = Document(stream)
        except (BadZipFile, KeyError, OpcError, ValueError, XMLSyntaxError) as error:
            raise InvalidDocxError from error

        blocks: list[str] = []
        for block in document.iter_inner_content():
            text = _block_text(block).strip()
            if text:
                blocks.append(text)

        text = normalize_extracted_text("\n".join(blocks))
        if not text:
            raise NoExtractableDocxTextError
        return ExtractedDocxText(text=text)
    finally:
        stream.seek(0, SEEK_SET)


def _block_text(block: Paragraph | Table) -> str:
    if isinstance(block, Paragraph):
        return block.text

    rows = ("\t".join(cell.text.strip() for cell in row.cells).strip() for row in block.rows)
    return "\n".join(row for row in rows if row)
