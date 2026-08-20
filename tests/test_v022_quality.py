from pathlib import Path

from kaic_zotero_push.extractors import extract_document
from kaic_zotero_push.models import Decision, ReferenceRecord
from kaic_zotero_push.parsing import parse_candidate

_FIXTURE = Path(__file__).parent / "fixtures" / "v022_review_cases.txt"


def _fixture_records() -> list[ReferenceRecord]:
    extracted = extract_document(_FIXTURE)
    return [
        parse_candidate(
            candidate.raw_text,
            source_index=candidate.source_index,
            source_locator=candidate.source_locator,
            section_confirmed=candidate.section_confirmed,
        )
        for candidate in extracted.candidates
    ]


def test_v022_fixture_when_extracted_contains_all_six_review_cases() -> None:
    # Given / When
    extracted = extract_document(_FIXTURE)

    # Then
    assert len(extracted.candidates) == 6


def test_v022_fixture_when_reports_are_parsed_preserves_source_metadata() -> None:
    # Given / When
    records = _fixture_records()

    # Then
    oecd, ministry, _, kchs, valuation, _ = records
    assert oecd.decision is Decision.CREATE
    assert oecd.parsed.item_type == "report"
    assert oecd.parsed.title == "Suicide Rates (Indicator)"
    assert oecd.parsed.creators[0].name == "OECD"
    assert oecd.parsed.publisher == "OECD Publishing"
    assert oecd.parsed.place == "Paris, France"
    assert oecd.parsed.date == "2024"
    assert oecd.parsed.doi == "10.1787/a82f3459-en"

    assert ministry.decision is Decision.CREATE
    assert ministry.parsed.item_type == "report"
    assert ministry.parsed.creators[0].name == (
        "Ministry of Health and Welfare (Republic of Korea)"
    )
    assert ministry.parsed.publisher == "MOHW"
    assert ministry.parsed.place == "Sejong, Republic of Korea"
    assert ministry.parsed.date == "2023"

    assert kchs.decision is Decision.CREATE
    assert kchs.parsed.item_type == "report"
    assert kchs.parsed.creators[0].name == "Korea Disease Control and Prevention Agency"
    assert kchs.parsed.publisher == "KDCA"
    assert kchs.parsed.place == "Cheongju, Republic of Korea"
    assert kchs.parsed.date == "2023"
    assert kchs.parsed.url == "https://chs.kdca.go.kr/chs/mnl/mnlBoardMain.do"

    assert valuation.decision is Decision.CREATE
    assert valuation.parsed.item_type == "report"
    assert valuation.parsed.title == "EQ-5D Korean Valuation Study Using Time Trade-Off Method"
    assert valuation.parsed.publisher == "Korea Centers for Disease Control and Prevention"
    assert valuation.parsed.place == "Seoul, Republic of Korea"
    assert valuation.parsed.date == "2007"
    assert [creator.last_name for creator in valuation.parsed.creators] == [
        "Nam",
        "Kim",
        "Kwon",
        "Koh",
        "Kind",
    ]


def test_v022_fixture_when_journal_tail_is_sparse_or_noisy_parses_core_fields() -> None:
    # Given / When
    records = _fixture_records()

    # Then
    choi = records[2]
    assert choi.decision is Decision.CREATE
    assert choi.parsed.title == (
        "Social isolation and suicidal ideation among older adults in Korea: "
        "the role of community welfare spending and community trust"
    )
    assert choi.parsed.container_title == "Res. Aging"
    assert choi.parsed.date == "2026"
    assert choi.parsed.volume is None
    assert choi.parsed.pages is None

    pullenayegum = records[5]
    assert pullenayegum.decision is Decision.CREATE
    assert pullenayegum.parsed.title == (
        "Analysis of health utility data when some subjects attain the upper bound of 1: "
        "Are Tobit and CLAD models appropriate"
    )
    assert pullenayegum.parsed.container_title == "Value Health"
    assert pullenayegum.parsed.date == "2010"
    assert pullenayegum.parsed.volume == "13"
    assert pullenayegum.parsed.pages == "487\N{EN DASH}494"
    assert pullenayegum.parsed.creators[-1].last_name == "O'Reilly"
    assert pullenayegum.parsed.doi == "10.1111/j.1524-4733.2010.00695.x"


def test_report_candidate_when_structure_is_incomplete_stays_in_review() -> None:
    # Given
    raw = "Agency. Incomplete Indicator."

    # When
    record = parse_candidate(raw, source_index=1, source_locator="paragraph=1")

    # Then
    assert record.decision is Decision.NEEDS_REVIEW
    assert record.parsed.item_type == "report"
    assert set(record.quality.warnings) == {
        "unparsed_citation_title",
        "missing_creators",
        "missing_year",
        "missing_publisher",
    }
