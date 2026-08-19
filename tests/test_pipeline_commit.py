from pathlib import Path
from typing import final

from kaic_zotero_push.approval import approve_manifest
from kaic_zotero_push.models import Approval, ExistingItem, Manifest, OutcomeStatus
from kaic_zotero_push.pipeline import CommitRequest, commit_run
from kaic_zotero_push.runs import write_model
from kaic_zotero_push.zotero.models import (
    Collection,
    KeyAccess,
    RemoteItem,
    ZoteroItemPayload,
    ZoteroResponsePayload,
)


@final
class FakeZoteroGateway:
    def __init__(self, *, user_id: int, collection_key: str) -> None:
        self.user_id = user_id
        self.collection_key = collection_key
        self.created_payloads: list[ZoteroItemPayload] = []

    def current_key(self) -> KeyAccess:
        return KeyAccess(user_id=self.user_id, username="tester", can_write=True)

    def list_collections(self, user_id: int) -> list[Collection]:
        assert user_id == self.user_id
        return [Collection(key=self.collection_key, name="Target")]

    def list_existing_items(self, user_id: int) -> list[ExistingItem]:
        assert user_id == self.user_id
        return []

    def get_template(self, item_type: str) -> ZoteroItemPayload:
        return ZoteroItemPayload(
            root={
                "itemType": item_type,
                "title": "",
                "creators": [],
                "date": "",
                "publicationTitle": "",
                "DOI": "",
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
        assert user_id == self.user_id
        assert len(write_token) == 32
        self.created_payloads.extend(items)
        return ZoteroResponsePayload(root={"successful": {"0": {"key": "ITEM1", "version": 1}}})

    def get_item(self, user_id: int, item_key: str) -> RemoteItem:
        assert user_id == self.user_id
        return RemoteItem(
            key=item_key,
            item_type="journalArticle",
            title="Example title",
            date="2025",
            first_creator="Smith",
            collections=[self.collection_key],
        )


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
