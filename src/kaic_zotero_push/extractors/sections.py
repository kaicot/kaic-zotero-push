"""Reference-section boundary detection for document inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from docx.document import Document

type LocatedParagraph = tuple[int, str]

_REFERENCE_HEADINGS: Final = frozenset({"references", "bibliography", "참고문헌"})


def is_reference_heading(text: str) -> bool:
    """Return whether a standalone line names a references section."""
    return text.strip().rstrip(":").casefold() in _REFERENCE_HEADINGS


def reference_paragraphs(document: Document) -> tuple[bool, list[LocatedParagraph]]:
    """Select paragraphs inside a confirmed DOCX references section."""
    start_index: int | None = None
    selected: list[LocatedParagraph] = []
    for paragraph_index, paragraph in enumerate(document.paragraphs, start=1):
        text = paragraph.text.strip()
        if not text:
            continue
        if start_index is None:
            if is_reference_heading(text):
                start_index = paragraph_index
            continue
        style_name = (paragraph.style.name or "") if paragraph.style is not None else ""
        if style_name.casefold().startswith("heading"):
            break
        selected.append((paragraph_index, text))
    return start_index is not None, selected
