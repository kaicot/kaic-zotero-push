from pathlib import Path

import pytest

from kaic_zotero_push.approval import approve_manifest
from kaic_zotero_push.errors import RunStateError
from kaic_zotero_push.models import Manifest, OutcomeStatus
from kaic_zotero_push.pipeline import CommitRequest, commit_run
from kaic_zotero_push.runs import write_model
from tests.fake_gateway import FakeZoteroGateway


def _collection_manifest(input_hash: str, *, with_record: bool) -> Manifest:
    records = (
        [
            {
                "source": {
                    "source_index": 1,
                    "source_locator": "line=1",
                    "raw_text": "Smith, J. (2025). Example title. Journal.",
                },
                "parsed": {
                    "item_type": "journalArticle",
                    "title": "Example title",
                    "creators": [{"last_name": "Smith", "first_name": "J"}],
                    "date": "2025",
                },
                "quality": {"parse_status": "parsed", "confidence": 0.9},
                "decision": "create",
            }
        ]
        if with_record
        else []
    )
    return Manifest.model_validate(
        {
            "input_path": "references.txt",
            "input_sha256": input_hash * 64,
            "target": {
                "user_id": 123,
                "collection_name": "New Collection",
                "create_collection": True,
            },
            "records": records,
        }
    )


def test_commit_run_when_approved_collection_is_missing_creates_it_once(
    tmp_path: Path,
) -> None:
    # Given
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = _collection_manifest("d", with_record=True)
    write_model(run_dir / "manifest.json", manifest)
    write_model(run_dir / "approval.json", approve_manifest(manifest))
    gateway = FakeZoteroGateway(user_id=123, collection_key=None)

    # When
    first_receipt = commit_run(CommitRequest(run_dir=run_dir), gateway)
    (run_dir / "receipt.json").unlink()
    second_receipt = commit_run(CommitRequest(run_dir=run_dir), gateway)

    # Then
    assert first_receipt.outcomes[0].status is OutcomeStatus.CREATED_VERIFIED
    assert second_receipt.outcomes[0].status is OutcomeStatus.CREATED_VERIFIED
    assert gateway.created_collections == ["New Collection"]
    assert gateway.created_payloads[0].root["collections"] == ["NEWCOLL"]


def test_commit_run_when_matching_collection_appears_before_commit_reuses_it(
    tmp_path: Path,
) -> None:
    # Given
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = _collection_manifest("e", with_record=False)
    write_model(run_dir / "manifest.json", manifest)
    write_model(run_dir / "approval.json", approve_manifest(manifest))
    gateway = FakeZoteroGateway(
        user_id=123,
        collection_key="EXISTING",
        collection_name="New Collection",
    )

    # When
    _ = commit_run(CommitRequest(run_dir=run_dir), gateway)

    # Then
    assert gateway.created_collections == []


def test_commit_run_when_collection_result_is_unknown_reconciles_exact_name(
    tmp_path: Path,
) -> None:
    # Given
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = _collection_manifest("f", with_record=False)
    write_model(run_dir / "manifest.json", manifest)
    write_model(run_dir / "approval.json", approve_manifest(manifest))
    gateway = FakeZoteroGateway(
        user_id=123,
        collection_key=None,
        unknown_collection_result=True,
    )

    # When
    _ = commit_run(CommitRequest(run_dir=run_dir), gateway)

    # Then
    assert gateway.created_collections == ["New Collection"]


def test_commit_run_when_approval_is_missing_does_not_create_collection(
    tmp_path: Path,
) -> None:
    # Given
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = _collection_manifest("1", with_record=False)
    write_model(run_dir / "manifest.json", manifest)
    gateway = FakeZoteroGateway(user_id=123, collection_key=None)

    # When / Then
    with pytest.raises(RunStateError):
        _ = commit_run(CommitRequest(run_dir=run_dir), gateway)
    assert gateway.created_collections == []
