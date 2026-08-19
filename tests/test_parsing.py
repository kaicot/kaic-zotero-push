from kaic_zotero_push.models import Decision, ParseStatus
from kaic_zotero_push.parsing import normalize_doi, normalize_title, parse_candidate


def test_normalize_doi_when_url_prefix_present() -> None:
    # Given
    raw = "https://doi.org/10.1000/Example."

    # When
    normalized = normalize_doi(raw)

    # Then
    assert normalized == "10.1000/example"


def test_parse_candidate_when_apa_reference_has_doi() -> None:
    # Given
    raw = (
        "Smith, J., & Kim, H. (2025). Effect of meaningful activity on recovery. "
        "Journal of Occupational Science, 12(3), 101-110. "
        "https://doi.org/10.1000/example"
    )

    # When
    record = parse_candidate(raw, source_index=1, source_locator="paragraph=1")

    # Then
    assert record.quality.parse_status is ParseStatus.PARSED
    assert record.decision is Decision.CREATE
    assert record.parsed.item_type == "journalArticle"
    assert record.parsed.title == "Effect of meaningful activity on recovery"
    assert record.parsed.doi == "10.1000/example"
    assert record.parsed.date == "2025"


def test_normalize_title_when_unicode_and_punctuation_differ() -> None:
    # Given
    title = "  Effects—of   Occupation: A Study! "

    # When
    normalized = normalize_title(title)

    # Then
    assert normalized == "effects of occupation a study"
