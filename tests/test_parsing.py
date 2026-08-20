from kaic_zotero_push.citation_parsers import parse_creators
from kaic_zotero_push.models import Decision, ParseStatus, StructuredReference
from kaic_zotero_push.parsing import normalize_doi, normalize_title, parse_candidate


def test_normalize_doi_when_url_prefix_present() -> None:
    # Given
    raw = "https://doi.org/10.1000/Example."

    # When
    normalized = normalize_doi(raw)

    # Then
    assert normalized == "10.1000/example"


def test_parse_creators_when_personal_authors_use_and_preserves_both() -> None:
    # Given
    raw = "Smith, J. and Doe, A."

    # When
    creators = parse_creators(raw)

    # Then
    assert [(creator.last_name, creator.first_name) for creator in creators] == [
        ("Smith", "J."),
        ("Doe", "A."),
    ]


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
    assert len(record.parsed.creators) == 2
    assert record.parsed.container_title == "Journal of Occupational Science"
    assert record.parsed.volume == "12"
    assert record.parsed.issue == "3"
    assert record.parsed.pages == "101-110"


def test_normalize_title_when_unicode_and_punctuation_differ() -> None:
    # Given
    title = "  Effects—of   Occupation: A Study! "

    # When
    normalized = normalize_title(title)

    # Then
    assert normalized == "effects of occupation a study"


def test_parse_candidate_when_mdpi_reference_has_semicolon_authors() -> None:
    # Given
    raw = (
        "Park, E.-Y.; Choi, S.-Y.; Kim, J.-H. "
        "Community participation after stroke. "
        "Front. Public Health 2026, 13, 1710375. "
        "https://doi.org/10.3389/fpubh.2025.1710375"
    )

    # When
    record = parse_candidate(raw, source_index=1, source_locator="paragraph=10")

    # Then
    assert record.decision is Decision.CREATE
    assert record.parsed.title == "Community participation after stroke"
    assert record.parsed.container_title == "Front. Public Health"
    assert record.parsed.date == "2026"
    assert record.parsed.volume == "13"
    assert record.parsed.issue is None
    assert record.parsed.pages == "1710375"
    assert record.parsed.doi == "10.3389/fpubh.2025.1710375"
    assert [(creator.last_name, creator.first_name) for creator in record.parsed.creators] == [
        ("Park", "E.-Y."),
        ("Choi", "S.-Y."),
        ("Kim", "J.-H."),
    ]


def test_parse_candidate_when_mdpi_reference_has_issue_and_article_number() -> None:
    # Given
    raw = (
        "Smith, J.; Doe, A. Occupational outcomes improve. "
        "J. Clin. Med. 2024, 13, 2, e70049. doi:10.3390/jcm1302e70049"
    )

    # When
    record = parse_candidate(raw, source_index=2, source_locator="paragraph=11")

    # Then
    assert record.decision is Decision.CREATE
    assert record.parsed.container_title == "J. Clin. Med."
    assert record.parsed.volume == "13"
    assert record.parsed.issue == "2"
    assert record.parsed.pages == "e70049"
    assert "10.3390" not in record.parsed.title


def test_parse_candidate_when_mdpi_reference_has_institution_author() -> None:
    # Given
    raw = (
        "World Health Organization. Global rehabilitation outcomes. "
        "WHO Technical Report Series 2024, 12, 106312."
    )

    # When
    record = parse_candidate(raw, source_index=3, source_locator="paragraph=12")

    # Then
    assert record.decision is Decision.CREATE
    assert record.parsed.creators[0].name == "World Health Organization"
    assert record.parsed.title == "Global rehabilitation outcomes"
    assert record.parsed.pages == "106312"


def test_parse_candidate_when_unstructured_journal_lacks_metadata_requires_review() -> None:
    # Given
    raw = "A title with no authors or journal. https://doi.org/10.1000/weak"

    # When
    record = parse_candidate(raw, source_index=4, source_locator="paragraph=13")

    # Then
    assert record.decision is Decision.NEEDS_REVIEW
    assert set(record.quality.warnings) == {
        "unparsed_citation_title",
        "missing_creators",
        "missing_publication_title",
    }


def test_parse_candidate_when_structured_report_preserves_institution_fields() -> None:
    # Given
    structured = StructuredReference(
        title="2022 KCHS 원자료 이용지침 및 참고자료",
        author="질병관리청",
        year="2022",
        publisher="질병관리청",
        url="https://example.org/kchs",
        item_type="report",
    )

    # When
    record = parse_candidate(
        "structured report",
        source_index=5,
        source_locator="row=2",
        structured=structured,
    )

    # Then
    assert record.decision is Decision.CREATE
    assert record.parsed.item_type == "report"
    assert record.parsed.creators[0].name == "질병관리청"
    assert record.parsed.publisher == "질병관리청"
    assert record.parsed.url == "https://example.org/kchs"


def test_parse_candidate_when_unstructured_report_preserves_institution_fields() -> None:
    # Given
    raw = (
        "질병관리청. 2022 KCHS 원자료 이용지침 및 참고자료 보고서. "
        "질병관리청, 2022. https://example.org/kchs"
    )

    # When
    record = parse_candidate(raw, source_index=6, source_locator="paragraph=20")

    # Then
    assert record.decision is Decision.CREATE
    assert record.parsed.item_type == "report"
    assert record.parsed.creators[0].name == "질병관리청"
    assert record.parsed.title == "2022 KCHS 원자료 이용지침 및 참고자료 보고서"
    assert record.parsed.date == "2022"
    assert record.parsed.publisher == "질병관리청"
    assert record.parsed.url == "https://example.org/kchs"
