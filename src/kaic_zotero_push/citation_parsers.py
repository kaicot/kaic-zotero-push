"""Format-specific parsers for unstructured journal citations."""

from __future__ import annotations

import re
from typing import Final

from kaic_zotero_push.models import Creator, ParsedReference

_YEAR: Final = r"(?:19|20)\d{2}"
_TAIL_WITH_ISSUE: Final = 3
_MINIMUM_TAIL_PARTS: Final = 2
_MDPI_PATTERN = re.compile(
    "".join(
        (
            r"^(?P<authors>.+?)\.\s+(?P<title>.+?)\.\s+",
            rf"(?P<journal>.+?)\s+(?P<year>{_YEAR})\s*,\s*(?P<tail>.+?)\.?$",
        )
    )
)
_VANCOUVER_PATTERN = re.compile(
    "".join(
        (
            r"^(?P<authors>.+?)\.\s+(?P<title>.+?)\.\s+",
            rf"(?P<journal>.+?)\.?\s+(?P<year>{_YEAR});",
            r"(?P<volume>[^(:;\s]+)(?:\((?P<issue>[^)]+)\))?:(?P<pages>[^.\s]+)\.?$",
        )
    )
)
_APA_PATTERN = re.compile(rf"^(?P<authors>.+?)\s*\((?P<year>{_YEAR})\)\.?\s*(?P<body>.+)$")
_APA_JOURNAL_PREFIX: Final = r"^(?P<journal>.+?),\s*(?P<volume>[^,(\s]+)"
_APA_JOURNAL_SUFFIX: Final = r"(?:\((?P<issue>[^)]+)\))?,\s*(?P<pages>[^.]+)\.?$"
_APA_JOURNAL_PATTERN = re.compile(f"{_APA_JOURNAL_PREFIX}{_APA_JOURNAL_SUFFIX}")
_REPORT_PATTERN = re.compile(
    "".join(
        (
            r"^(?P<authors>.+?)\.\s+(?P<title>.+?)\.\s+",
            rf"(?P<publisher>.+?),\s*(?P<year>{_YEAR})\.?$",
        )
    )
)


def parse_creators(raw: str | None) -> list[Creator]:
    """Parse personal or institutional creators without inventing names."""
    if raw is None or not raw.strip():
        return []
    creators: list[Creator] = []
    for segment in re.split(r"\s*(?:;|&|\band\b)\s*", raw.strip().rstrip(".")):
        cleaned = segment.strip(" ,")
        if not cleaned:
            continue
        last_name, separator, first_name = cleaned.partition(",")
        if separator:
            normalized_first = first_name.strip()
            if (
                normalized_first
                and normalized_first[-1].isupper()
                and all(character.isupper() or character in ".-" for character in normalized_first)
            ):
                normalized_first = f"{normalized_first}."
            creators.append(Creator(last_name=last_name.strip(), first_name=normalized_first))
        else:
            creators.append(Creator(name=cleaned))
    return creators


def _journal_reference(
    match: re.Match[str],
    *,
    doi: str | None,
    url: str | None,
) -> ParsedReference:
    tail = [part.strip() for part in match.group("tail").rstrip(".").split(",")]
    volume = tail[0] if tail else None
    issue = tail[1] if len(tail) == _TAIL_WITH_ISSUE else None
    pages = tail[-1] if len(tail) >= _MINIMUM_TAIL_PARTS else None
    return ParsedReference(
        item_type="journalArticle",
        title=match.group("title").strip(),
        creators=parse_creators(match.group("authors")),
        date=match.group("year"),
        container_title=match.group("journal").strip(),
        volume=volume,
        issue=issue,
        pages=pages,
        doi=doi,
        url=url,
    )


def parse_mdpi_vancouver(
    text: str,
    *,
    doi: str | None,
    url: str | None,
) -> ParsedReference | None:
    """Parse MDPI comma-tail or Vancouver semicolon-tail journal citations."""
    mdpi_match = _MDPI_PATTERN.match(text)
    if mdpi_match is not None:
        tail_count = len(mdpi_match.group("tail").split(","))
        if tail_count in {2, 3}:
            return _journal_reference(mdpi_match, doi=doi, url=url)
    vancouver_match = _VANCOUVER_PATTERN.match(text)
    if vancouver_match is None:
        return None
    return ParsedReference(
        item_type="journalArticle",
        title=vancouver_match.group("title").strip(),
        creators=parse_creators(vancouver_match.group("authors")),
        date=vancouver_match.group("year"),
        container_title=vancouver_match.group("journal").strip(),
        volume=vancouver_match.group("volume"),
        issue=vancouver_match.group("issue"),
        pages=vancouver_match.group("pages"),
        doi=doi,
        url=url,
    )


def parse_apa(
    text: str,
    *,
    doi: str | None,
    url: str | None,
) -> ParsedReference | None:
    """Parse the supported APA author-year journal form."""
    match = _APA_PATTERN.match(text)
    if match is None:
        return None
    title, separator, publication = match.group("body").partition(". ")
    publication_match = _APA_JOURNAL_PATTERN.match(publication.strip()) if separator else None
    return ParsedReference(
        item_type="journalArticle",
        title=title.strip().rstrip("."),
        creators=parse_creators(match.group("authors")),
        date=match.group("year"),
        container_title=(
            publication_match.group("journal").strip()
            if publication_match is not None
            else publication.strip().rstrip(".") or None
        ),
        volume=publication_match.group("volume") if publication_match is not None else None,
        issue=publication_match.group("issue") if publication_match is not None else None,
        pages=(publication_match.group("pages").strip() if publication_match is not None else None),
        doi=doi,
        url=url,
    )


def parse_report(
    text: str,
    *,
    url: str | None,
) -> ParsedReference | None:
    """Parse an institution-authored report citation."""
    match = _REPORT_PATTERN.match(text)
    if match is None:
        return None
    return ParsedReference(
        item_type="report",
        title=match.group("title").strip(),
        creators=parse_creators(match.group("authors")),
        date=match.group("year"),
        publisher=match.group("publisher").strip(),
        url=url,
    )
