from pathlib import Path
from typing import final

from pydantic import TypeAdapter

from kaic_zotero_push.approval import approve_manifest
from kaic_zotero_push.dedup import classify_duplicates
from kaic_zotero_push.extractors import extract_document
from kaic_zotero_push.models import (
    Decision,
    ExistingItem,
    JsonValue,
    Manifest,
    OutcomeStatus,
    ReferenceRecord,
    TargetLibrary,
)
from kaic_zotero_push.parsing import parse_candidate
from kaic_zotero_push.pipeline import CommitRequest, commit_run
from kaic_zotero_push.runs import write_model
from kaic_zotero_push.zotero.models import (
    Collection,
    KeyAccess,
    RemoteItem,
    ZoteroItemPayload,
    ZoteroResponsePayload,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "v02_references.txt"
_STRING: TypeAdapter[str] = TypeAdapter(str)
_OPTIONAL_STRING: TypeAdapter[str | None] = TypeAdapter(str | None)
_STRING_LIST: TypeAdapter[list[str]] = TypeAdapter(list[str])


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


@final
class FixtureGateway:
    def __init__(self, existing_items: list[ExistingItem]) -> None:
        self.existing_items = existing_items
        self.created_payloads: list[ZoteroItemPayload] = []
        self.read_keys: list[str] = []

    def current_key(self) -> KeyAccess:
        return KeyAccess(user_id=123, username="tester", can_write=True)

    def list_collections(self, user_id: int) -> list[Collection]:
        assert user_id == 123
        return []

    def create_collection(
        self,
        user_id: int,
        name: str,
        write_token: str,
    ) -> Collection:
        raise AssertionError((user_id, name, write_token))

    def list_existing_items(self, user_id: int) -> list[ExistingItem]:
        assert user_id == 123
        return self.existing_items

    def get_template(self, item_type: str) -> ZoteroItemPayload:
        return ZoteroItemPayload(
            root={
                "itemType": item_type,
                "title": "",
                "creators": [],
                "date": "",
                "publicationTitle": "",
                "volume": "",
                "issue": "",
                "pages": "",
                "publisher": "",
                "DOI": "",
                "url": "",
                "collections": [],
                "tags": [],
            }
        )

    def create_items(
        self,
        user_id: int,
        items: list[ZoteroItemPayload],
        write_token: str,
    ) -> ZoteroResponsePayload:
        assert user_id == 123
        assert len(write_token) == 32
        start = len(self.created_payloads)
        self.created_payloads.extend(items)
        successes: dict[str, JsonValue] = {
            str(index): f"ITEM{start + index}" for index in range(len(items))
        }
        return ZoteroResponsePayload(root={"success": successes, "failed": {}})

    def get_item(self, user_id: int, item_key: str) -> RemoteItem:
        assert user_id == 123
        self.read_keys.append(item_key)
        index = int(item_key.removeprefix("ITEM"))
        payload = self.created_payloads[index].root
        return RemoteItem(
            key=item_key,
            item_type=_STRING.validate_python(payload["itemType"]),
            title=_STRING.validate_python(payload["title"]),
            doi=_OPTIONAL_STRING.validate_python(payload.get("DOI")),
            collections=_STRING_LIST.validate_python(payload["collections"]),
        )


def test_v02_fixture_extracts_exactly_twenty_seven_references() -> None:
    # Given / When
    extracted = extract_document(_FIXTURE)

    # Then
    assert len(extracted.candidates) == 27
    assert all(candidate.raw_text != "References" for candidate in extracted.candidates)


def test_v02_fixture_parses_journal_and_report_metadata() -> None:
    # Given / When
    records = _fixture_records()

    # Then
    journals = records[:24]
    reports = records[24:]
    assert all(record.decision is Decision.CREATE for record in records)
    assert all(record.parsed.creators for record in journals)
    assert all(record.parsed.date for record in journals)
    assert all(record.parsed.container_title for record in journals)
    assert all(record.parsed.volume and record.parsed.pages for record in journals)
    assert all(record.parsed.item_type == "report" for record in reports)
    assert all(record.parsed.creators for record in reports)
    assert all(record.parsed.publisher and record.parsed.url for record in reports)


def test_v02_fixture_classifies_four_existing_items_without_recreating() -> None:
    # Given
    records = _fixture_records()
    existing = [
        ExistingItem(key=f"EXISTING{index}", parsed=records[index].parsed) for index in range(4)
    ]

    # When
    classified = classify_duplicates(records, existing)

    # Then
    assert sum(record.decision is Decision.DUPLICATE_SKIPPED for record in classified) == 4
    assert sum(record.decision is Decision.CREATE for record in classified[:24]) == 20
    assert sum(record.decision is Decision.CREATE for record in classified[24:]) == 3


def test_v02_fixture_writes_twenty_three_items_and_persists_receipt(
    tmp_path: Path,
) -> None:
    # Given
    records = _fixture_records()
    existing = [
        ExistingItem(key=f"EXISTING{index}", parsed=records[index].parsed) for index in range(4)
    ]
    manifest = Manifest.build(
        input_path=_FIXTURE,
        input_sha256="2" * 64,
        target=TargetLibrary(user_id=123),
        records=records,
    )
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    write_model(run_dir / "manifest.json", manifest)
    write_model(run_dir / "approval.json", approve_manifest(manifest))
    gateway = FixtureGateway(existing)

    # When
    receipt = commit_run(CommitRequest(run_dir=run_dir), gateway)

    # Then
    assert (
        sum(outcome.status is OutcomeStatus.CREATED_VERIFIED for outcome in receipt.outcomes) == 23
    )
    assert (
        sum(outcome.status is OutcomeStatus.DUPLICATE_SKIPPED for outcome in receipt.outcomes) == 4
    )
    assert len(gateway.created_payloads) == 23
    assert len(gateway.read_keys) == 23
    assert (run_dir / "receipt.json").is_file()
