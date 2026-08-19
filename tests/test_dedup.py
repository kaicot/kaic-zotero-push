from kaic_zotero_push.dedup import classify_duplicates
from kaic_zotero_push.models import (
    Decision,
    ExistingItem,
    ParsedReference,
    ReferenceRecord,
)
from kaic_zotero_push.parsing import parse_candidate


def test_classify_duplicates_when_doi_matches() -> None:
    # Given
    candidate = parse_candidate(
        "Smith, J. (2025). Example title. Example Journal. doi:10.1000/EXAMPLE",
        source_index=1,
        source_locator="line=1",
    )
    existing = [
        ExistingItem(
            key="ABC123",
            parsed=ParsedReference(
                item_type="journalArticle",
                title="Different display title",
                date="2024",
                doi="10.1000/example",
            ),
        )
    ]

    # When
    result = classify_duplicates([candidate], existing)

    # Then
    assert result[0].decision is Decision.DUPLICATE_SKIPPED
    assert result[0].duplicate.matched_item_key == "ABC123"


def test_classify_duplicates_when_title_similarity_is_ambiguous() -> None:
    # Given
    candidate: ReferenceRecord = parse_candidate(
        "Smith, J. (2025). Effects of occupation on recovery. Journal.",
        source_index=1,
        source_locator="line=1",
    )
    existing = [
        ExistingItem(
            key="POSSIBLE1",
            parsed=ParsedReference(
                item_type="journalArticle",
                title="The effects of occupation on recovery",
                date="2024",
            ),
        )
    ]

    # When
    result = classify_duplicates([candidate], existing)

    # Then
    assert result[0].decision is Decision.NEEDS_REVIEW
    assert result[0].duplicate.matched_item_key == "POSSIBLE1"
