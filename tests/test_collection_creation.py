from pathlib import Path
from typing import final

from kaic_zotero_push.models import (
    ExistingItem,
    Manifest,
    TargetLibrary,
)
from kaic_zotero_push.planning import PreviewRequest, prepare_run
from kaic_zotero_push.zotero.models import (
    Collection,
    KeyAccess,
    RemoteItem,
    ZoteroItemPayload,
    ZoteroResponsePayload,
)


@final
class MissingCollectionGateway:
    create_calls: int = 0

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
        assert user_id == 123
        assert len(write_token) == 32
        self.create_calls += 1
        return Collection(key="NEWCOLL", name=name)

    def list_existing_items(self, user_id: int) -> list[ExistingItem]:
        assert user_id == 123
        return []

    def get_template(self, item_type: str) -> ZoteroItemPayload:
        raise AssertionError(item_type)

    def create_items(
        self,
        user_id: int,
        items: list[ZoteroItemPayload],
        write_token: str,
    ) -> ZoteroResponsePayload:
        raise AssertionError((user_id, items, write_token))

    def get_item(self, user_id: int, item_key: str) -> RemoteItem:
        raise AssertionError((user_id, item_key))


def test_prepare_run_when_collection_is_missing_records_creation_intent_without_writing(
    tmp_path: Path,
) -> None:
    # Given
    source = tmp_path / "references.txt"
    _ = source.write_text(
        "Smith, J. (2025). Example title. Example Journal, 1(1), 1-2.",
        encoding="utf-8",
    )
    gateway = MissingCollectionGateway()

    # When
    prepared = prepare_run(
        PreviewRequest(
            input_path=source,
            runs_dir=tmp_path / "runs",
            offline=False,
            collection_name="New Collection",
        ),
        gateway,
    )

    # Then
    assert prepared.manifest.target.collection_key is None
    assert prepared.manifest.target.collection_name == "New Collection"
    assert prepared.manifest.target.create_collection is True
    assert gateway.create_calls == 0


def test_approval_binding_when_collection_creation_name_changes_is_different() -> None:
    # Given
    first = Manifest.build(
        input_path=Path("references.txt"),
        input_sha256="a" * 64,
        target=TargetLibrary(
            user_id=123,
            collection_name="First",
            create_collection=True,
        ),
        records=[],
    )
    second = first.model_copy(
        update={
            "target": TargetLibrary(
                user_id=123,
                collection_name="Second",
                create_collection=True,
            )
        }
    )

    # When
    first_binding = first.approval_binding()
    second_binding = second.approval_binding()

    # Then
    assert first_binding != second_binding
