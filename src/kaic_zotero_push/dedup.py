"""Deterministic local and remote duplicate classification."""

from typing import Final

from rapidfuzz.fuzz import ratio

from kaic_zotero_push.models import (
    Decision,
    DuplicateInfo,
    ExistingItem,
    ReferenceRecord,
)
from kaic_zotero_push.parsing import normalize_doi, normalize_title

_STRONG_TITLE_MATCH: Final = 95.0
_WEAK_TITLE_MATCH: Final = 90.0


def _exact_reason(candidate: ReferenceRecord, existing: ExistingItem) -> str | None:
    candidate_doi = normalize_doi(candidate.parsed.doi)
    existing_doi = normalize_doi(existing.parsed.doi)
    if candidate_doi and candidate_doi == existing_doi:
        return "doi"
    identifiers = (
        (candidate.parsed.pmid, existing.parsed.pmid, "pmid"),
        (candidate.parsed.isbn, existing.parsed.isbn, "isbn"),
    )
    for left, right, name in identifiers:
        if left and right and left.casefold() == right.casefold():
            return name
    same_title = normalize_title(candidate.parsed.title) == normalize_title(existing.parsed.title)
    same_year = candidate.parsed.year() == existing.parsed.year()
    same_creator = candidate.parsed.first_creator_key() == existing.parsed.first_creator_key()
    if same_title and same_year and same_creator and candidate.parsed.first_creator_key():
        return "title_year_first_creator"
    return None


def _possible(candidate: ReferenceRecord, existing: ExistingItem) -> bool:
    title_score = ratio(
        normalize_title(candidate.parsed.title),
        normalize_title(existing.parsed.title),
    )
    corroborated = candidate.parsed.year() == existing.parsed.year() or (
        bool(candidate.parsed.first_creator_key())
        and candidate.parsed.first_creator_key() == existing.parsed.first_creator_key()
    )
    return (title_score >= _STRONG_TITLE_MATCH and corroborated) or (
        title_score >= _WEAK_TITLE_MATCH
    )


def classify_duplicates(
    candidates: list[ReferenceRecord],
    existing_items: list[ExistingItem],
    *,
    target_collection_key: str | None = None,
    target_is_new_collection: bool = False,
) -> list[ReferenceRecord]:
    """Classify duplicates within the input and the target collection only."""
    classified: list[ReferenceRecord] = []
    if target_is_new_collection:
        remote_index: list[ExistingItem] = []
    elif target_collection_key is None:
        remote_index = [item for item in existing_items if not item.collections]
    else:
        remote_index = [
            item for item in existing_items if target_collection_key in item.collections
        ]
    document_index: list[ExistingItem] = []
    for candidate in candidates:
        local_exact = next(
            (
                (existing, reason)
                for existing in document_index
                if (reason := _exact_reason(candidate, existing)) is not None
            ),
            None,
        )
        local_possible = (
            None
            if local_exact is not None
            else next(
                (existing for existing in document_index if _possible(candidate, existing)),
                None,
            )
        )
        if local_exact is not None or local_possible is not None:
            if local_exact is not None:
                matched = local_exact[0]
                reason = "within_input_exact"
            elif local_possible is not None:
                matched = local_possible
                reason = "within_input_title_similarity"
            else:
                continue
            updated = candidate.model_copy(
                update={
                    "decision": Decision.NEEDS_REVIEW,
                    "duplicate": DuplicateInfo(
                        status="within_input",
                        matched_item_key=matched.key,
                        reason=reason,
                    ),
                }
            )
            classified.append(updated)
            document_index.append(
                ExistingItem(
                    key=f"source:{candidate.source.source_index}",
                    parsed=candidate.parsed,
                )
            )
            continue

        exact = next(
            (
                (existing, reason)
                for existing in remote_index
                if (reason := _exact_reason(candidate, existing)) is not None
            ),
            None,
        )
        if exact is not None:
            existing, reason = exact
            updated = candidate.model_copy(
                update={
                    "decision": Decision.DUPLICATE_SKIPPED,
                    "duplicate": DuplicateInfo(
                        status="exact",
                        matched_item_key=existing.key,
                        reason=reason,
                    ),
                }
            )
        else:
            possible = next(
                (existing for existing in remote_index if _possible(candidate, existing)),
                None,
            )
            if possible is None:
                updated = candidate
            else:
                updated = candidate.model_copy(
                    update={
                        "decision": Decision.NEEDS_REVIEW,
                        "duplicate": DuplicateInfo(
                            status="possible",
                            matched_item_key=possible.key,
                            reason="title_similarity",
                        ),
                    }
                )
        classified.append(updated)
        document_index.append(
            ExistingItem(
                key=f"source:{candidate.source.source_index}",
                parsed=candidate.parsed,
            )
        )
    return classified
