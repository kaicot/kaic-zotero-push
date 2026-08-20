from pathlib import Path

from kaic_zotero_push.approval import approve_manifest
from kaic_zotero_push.models import Approval, Manifest, OutcomeStatus
from kaic_zotero_push.pipeline import CommitRequest, commit_run
from kaic_zotero_push.runs import write_model
from tests.fake_gateway import FakeZoteroGateway


def test_commit_run_when_approved_item_is_created_and_verified(tmp_path: Path) -> None:
    # Given
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = Manifest.model_validate(
        {
            "input_path": "references.txt",
            "input_sha256": "a" * 64,
            "target": {"user_id": 123, "collection_key": "COLL1"},
            "records": [
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
            ],
        }
    )
    approval: Approval = approve_manifest(manifest)
    write_model(run_dir / "manifest.json", manifest)
    write_model(run_dir / "approval.json", approval)
    gateway = FakeZoteroGateway(user_id=123, collection_key="COLL1")

    # When
    receipt = commit_run(CommitRequest(run_dir=run_dir), gateway)

    # Then
    assert receipt.outcomes[0].status is OutcomeStatus.CREATED_VERIFIED
    assert len(gateway.created_payloads) == 1


def test_commit_run_when_verified_receipt_exists_does_not_create_again(
    tmp_path: Path,
) -> None:
    # Given
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = Manifest.model_validate(
        {
            "input_path": "references.txt",
            "input_sha256": "b" * 64,
            "target": {"user_id": 123, "collection_key": "COLL1"},
            "records": [
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
            ],
        }
    )
    write_model(run_dir / "manifest.json", manifest)
    write_model(run_dir / "approval.json", approve_manifest(manifest))
    gateway = FakeZoteroGateway(user_id=123, collection_key="COLL1")
    _ = commit_run(CommitRequest(run_dir=run_dir), gateway)

    # When
    receipt = commit_run(CommitRequest(run_dir=run_dir), gateway)

    # Then
    assert receipt.outcomes[0].status is OutcomeStatus.CREATED_VERIFIED
    assert len(gateway.created_payloads) == 1


def test_commit_run_when_receipt_is_missing_reuses_persisted_success_keys(
    tmp_path: Path,
) -> None:
    # Given
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = Manifest.model_validate(
        {
            "input_path": "references.txt",
            "input_sha256": "c" * 64,
            "target": {"user_id": 123, "collection_key": "COLL1"},
            "records": [
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
            ],
        }
    )
    write_model(run_dir / "manifest.json", manifest)
    write_model(run_dir / "approval.json", approve_manifest(manifest))
    gateway = FakeZoteroGateway(user_id=123, collection_key="COLL1")
    _ = commit_run(CommitRequest(run_dir=run_dir), gateway)
    (run_dir / "receipt.json").unlink()

    # When
    receipt = commit_run(CommitRequest(run_dir=run_dir), gateway)

    # Then
    assert receipt.outcomes[0].status is OutcomeStatus.CREATED_VERIFIED
    assert len(gateway.created_payloads) == 1
