"""Conservative citation parsing and comparison normalization."""

from __future__ import annotations

import re
import unicodedata
from typing import Final

from kaic_zotero_push.models import (
    Creator,
    Decision,
    ParsedReference,
    ParseStatus,
    Quality,
    ReferenceRecord,
    SourceCandidate,
    StructuredReference,
)

_DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", re.IGNORECASE)
_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)
_APA_PATTERN = re.compile(r"^(?P<authors>.+?)\s*\((?P<year>(?:19|20)\d{2})\)\.?\s*(?P<body>.+)$")
_NUMBER_PREFIX = re.compile(r"^\s*(?:\[\d+\]|\d+[.)])\s*")
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")
_NAME_PART_COUNT: Final = 2
_PARSED_THRESHOLD: Final = 0.8


def normalize_doi(raw: str | None) -> str | None:
    """Return a lowercase DOI comparison value."""
    if raw is None:
        return None
    match = _DOI_PATTERN.search(raw)
    if match is None:
        return None
    return match.group(0).rstrip(".,;").casefold()


def normalize_title(raw: str) -> str:
    """Return an NFKC, punctuation-free title comparison value."""
    normalized = unicodedata.normalize("NFKC", raw).casefold()
    normalized = normalized.replace("\u2014", " ").replace("\u2013", " ")
    return _SPACES.sub(" ", _PUNCTUATION.sub(" ", normalized)).strip()


def _parse_creators(raw: str | None) -> list[Creator]:
    if raw is None or not raw.strip():
        return []
    creators: list[Creator] = []
    for segment in re.split(r"\s*(?:&|;|\band\b)\s*", raw.strip().rstrip(".")):
        cleaned = segment.strip(" ,")
        if not cleaned:
            continue
        parts = [part.strip() for part in cleaned.split(",", maxsplit=1)]
        if len(parts) == _NAME_PART_COUNT:
            creators.append(Creator(last_name=parts[0], first_name=parts[1].strip(" .")))
        else:
            creators.append(Creator(name=cleaned))
    return creators


def _item_type(text: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    lowered = text.casefold()
    keywords = {
        "thesis": ("thesis", "dissertation", "학위논문"),
        "conferencePaper": ("conference", "proceedings", "학술대회"),
        "report": ("report", "보고서"),
        "preprint": ("preprint", "arxiv", "medrxiv", "biorxiv"),
        "book": ("isbn",),
    }
    for item_type, markers in keywords.items():
        if any(marker in lowered for marker in markers):
            return item_type
    if _URL_PATTERN.fullmatch(text.strip()) and normalize_doi(text) is None:
        return "webpage"
    return "journalArticle"


def _from_structured(structured: StructuredReference) -> ParsedReference:
    return ParsedReference(
        item_type=_item_type(structured.title or "", structured.item_type),
        title=(structured.title or "").strip(),
        creators=_parse_creators(structured.author),
        date=structured.year,
        container_title=structured.container_title,
        volume=structured.volume,
        issue=structured.issue,
        pages=structured.pages,
        publisher=structured.publisher,
        doi=normalize_doi(structured.doi),
        pmid=structured.pmid,
        isbn=structured.isbn,
        url=structured.url,
    )


def _extract_url(raw: str) -> str | None:
    match = _URL_PATTERN.search(raw)
    return match.group(0).rstrip(".,") if match is not None else None


def parse_candidate(
    raw_text: str,
    *,
    source_index: int,
    source_locator: str,
    structured: StructuredReference | None = None,
) -> ReferenceRecord:
    """Parse one candidate without inventing absent metadata."""
    source = SourceCandidate(
        source_index=source_index,
        source_locator=source_locator,
        raw_text=raw_text.strip(),
        structured=structured,
    )
    if structured is not None:
        parsed = _from_structured(structured)
    else:
        cleaned = _NUMBER_PREFIX.sub("", raw_text.strip())
        match = _APA_PATTERN.match(cleaned)
        if match is None:
            title = _URL_PATTERN.sub("", cleaned).strip(" .")
            parsed = ParsedReference(
                item_type=_item_type(cleaned),
                title=title,
                doi=normalize_doi(cleaned),
                url=_extract_url(cleaned),
            )
        else:
            body = match.group("body")
            segments = [segment.strip() for segment in body.split(".") if segment.strip()]
            title = segments[0] if segments else ""
            parsed = ParsedReference(
                item_type=_item_type(cleaned),
                title=title,
                creators=_parse_creators(match.group("authors")),
                date=match.group("year"),
                container_title=segments[1] if len(segments) > 1 else None,
                doi=normalize_doi(cleaned),
                url=_extract_url(cleaned),
            )
    has_core_fields = bool(parsed.title and (parsed.date or parsed.doi))
    confidence = 0.9 if has_core_fields else (0.6 if parsed.title else 0.2)
    status = ParseStatus.PARSED if confidence >= _PARSED_THRESHOLD else ParseStatus.NEEDS_REVIEW
    decision = Decision.CREATE if status is ParseStatus.PARSED else Decision.NEEDS_REVIEW
    warnings = [] if has_core_fields else ["missing_year_or_identifier"]
    return ReferenceRecord(
        source=source,
        parsed=parsed,
        quality=Quality(parse_status=status, confidence=confidence, warnings=warnings),
        decision=decision,
    )
