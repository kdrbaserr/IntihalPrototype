from __future__ import annotations

import re
import unicodedata

HORIZONTAL_WHITESPACE = re.compile(r"[^\S\n]+")


def normalize_extracted_text(text: str) -> str:
    """Clean extracted text without transliterating or case-folding Unicode letters."""

    normalized = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    without_controls = "".join(
        character
        if character == "\n" or not unicodedata.category(character).startswith("C")
        else " "
        for character in normalized
    )
    lines = (HORIZONTAL_WHITESPACE.sub(" ", line).strip() for line in without_controls.split("\n"))
    return "\n".join(lines).strip()
