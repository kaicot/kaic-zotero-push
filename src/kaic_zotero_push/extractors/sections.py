"""Reference-section boundary detection for document inputs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from docx.document import Document

type LocatedParagraph = tuple[int, str]

_REFERENCE_HEADINGS: Final = frozenset({"references", "bibliography", "참고문헌"})
_SECTION_TERMINATOR: Final = re.compile(
    r"""
    ^(?:
        table\s+(?:s\s*)?\d+\b
        |supplementary(?:\s+table\b.*)?\s*$
        |supporting\s+information\b
        |appendix\b
        |acknowledg(?:e)?ments\b
        |figure\b
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True, slots=True)
class ReferenceSection:
    """Paragraphs and confidence for one DOCX references section."""

    found: bool
    boundary_confirmed: bool
    paragraphs: tuple[LocatedParagraph, ...]


def is_reference_heading(text: str) -> bool:
    """Return whether a standalone line names a references section."""
    return text.strip().rstrip(":").casefold() in _REFERENCE_HEADINGS


def reference_paragraphs(document: Document) -> ReferenceSection:
    """Select paragraphs inside a confirmed DOCX references section."""
    found = False
    selected: list[LocatedParagraph] = []
    for paragraph_index, paragraph in enumerate(document.paragraphs, start=1):
        text = paragraph.text.strip()
        if not text:
            continue
        if not found:
            if is_reference_heading(text):
                found = True
            continue
        style_name = (paragraph.style.name or "") if paragraph.style is not None else ""
        if style_name.casefold().startswith("heading") or _SECTION_TERMINATOR.match(text):
            return ReferenceSection(
                found=True,
                boundary_confirmed=True,
                paragraphs=tuple(selected),
            )
        selected.append((paragraph_index, text))
    return ReferenceSection(
        found=found,
        boundary_confirmed=False,
        paragraphs=tuple(selected),
    )
