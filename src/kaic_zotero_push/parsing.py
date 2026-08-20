"""Conservative citation parsing and comparison normalization."""

from __future__ import annotations

import re
import unicodedata
from typing import Final

from kaic_zotero_push.citation_parsers import (
    parse_apa,
    parse_creators,
    parse_mdpi_vancouver,
    parse_report,
)
from kaic_zotero_push.models import (
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
_NUMBER_PREFIX = re.compile(r"^\s*(?:\[\d+\]|\d+[.)])\s*")
_DOI_LABEL = re.compile(r"\bdoi\s*:\s*", re.IGNORECASE)
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")
_PARSED_THRESHOLD: Final = 0.8
_REPORT_MARKERS: Final = (
    "press release",
    "user guide",
    "raw data",
    "reference materials",
    "indicator",
    "valuation study",
    "report",
    "보고서",
    "지침",
)


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


def _item_type(text: str, explicit: str | None = None) -> str:
    if explicit:
        return explicit
    lowered = text.casefold()
    keywords = {
        "thesis": ("thesis", "dissertation", "학위논문"),
        "conferencePaper": ("conference", "proceedings", "학술대회"),
        "preprint": ("preprint", "arxiv", "medrxiv", "biorxiv"),
        "book": ("isbn",),
    }
    if any(marker in lowered for marker in _REPORT_MARKERS):
        return "report"
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
        creators=parse_creators(structured.author),
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


def _without_identifiers(raw: str) -> str:
    without_urls = _URL_PATTERN.sub("", raw)
    without_doi = _DOI_PATTERN.sub("", without_urls)
    return _DOI_LABEL.sub("", without_doi).strip(" .")


def _journal_warnings(
    parsed: ParsedReference,
    source: SourceCandidate,
) -> list[str]:
    warnings: list[str] = []
    source_body = _without_identifiers(_NUMBER_PREFIX.sub("", source.raw_text))
    if source.structured is None and normalize_title(parsed.title) == normalize_title(source_body):
        warnings.append("unparsed_citation_title")
    if not parsed.creators:
        warnings.append("missing_creators")
    if not (parsed.date or parsed.doi):
        warnings.append("missing_year_or_identifier")
    if not parsed.container_title:
        warnings.append("missing_publication_title")
    if parsed.doi and parsed.doi.casefold() in parsed.title.casefold():
        warnings.append("doi_in_title")
    return warnings


def _report_warnings(
    parsed: ParsedReference,
    source: SourceCandidate,
) -> list[str]:
    warnings: list[str] = []
    source_body = _without_identifiers(_NUMBER_PREFIX.sub("", source.raw_text))
    if source.structured is None and normalize_title(parsed.title) == normalize_title(source_body):
        warnings.append("unparsed_citation_title")
    if not parsed.creators:
        warnings.append("missing_creators")
    if not parsed.date:
        warnings.append("missing_year")
    if not parsed.publisher:
        warnings.append("missing_publisher")
    return warnings


def _quality(parsed: ParsedReference, source: SourceCandidate) -> Quality:
    is_journal = parsed.item_type == "journalArticle"
    is_report = parsed.item_type == "report"
    warnings = (
        _journal_warnings(parsed, source)
        if is_journal
        else (_report_warnings(parsed, source) if is_report else [])
    )
    if not is_journal and not is_report and not parsed.title:
        warnings.append("missing_title")
    if not source.section_confirmed:
        warnings.append("unconfirmed_reference_section")
    confidence = 0.95 if not warnings else (0.6 if parsed.title else 0.2)
    status = ParseStatus.PARSED if confidence >= _PARSED_THRESHOLD else ParseStatus.NEEDS_REVIEW
    return Quality(parse_status=status, confidence=confidence, warnings=warnings)


def parse_candidate(
    raw_text: str,
    *,
    source_index: int,
    source_locator: str,
    structured: StructuredReference | None = None,
    section_confirmed: bool = True,
) -> ReferenceRecord:
    """Parse one candidate without inventing absent metadata."""
    source = SourceCandidate(
        source_index=source_index,
        source_locator=source_locator,
        raw_text=raw_text.strip(),
        structured=structured,
        section_confirmed=section_confirmed,
    )
    if structured is not None:
        parsed = _from_structured(structured)
    else:
        cleaned = _NUMBER_PREFIX.sub("", raw_text.strip())
        doi = normalize_doi(cleaned)
        url = _extract_url(cleaned)
        citation = _without_identifiers(cleaned)
        detected_type = _item_type(citation)
        parsed = (
            (parse_report(citation, doi=doi, url=url) if detected_type == "report" else None)
            or parse_mdpi_vancouver(citation, doi=doi, url=url)
            or parse_apa(citation, doi=doi, url=url)
            or ParsedReference(
                item_type=detected_type,
                title=citation,
                doi=doi,
                url=url,
            )
        )
    quality = _quality(parsed, source)
    decision = (
        Decision.CREATE if quality.parse_status is ParseStatus.PARSED else Decision.NEEDS_REVIEW
    )
    return ReferenceRecord(
        source=source,
        parsed=parsed,
        quality=quality,
        decision=decision,
    )
