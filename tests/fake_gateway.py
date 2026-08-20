from typing import final

from kaic_zotero_push.errors import ZoteroApiError
from kaic_zotero_push.models import ExistingItem
from kaic_zotero_push.zotero.models import (
    Collection,
    KeyAccess,
    RemoteItem,
    ZoteroItemPayload,
    ZoteroResponsePayload,
)


@final
class FakeZoteroGateway:
    def __init__(
        self,
        *,
        user_id: int,
        collection_key: str | None,
        collection_name: str = "Target",
        unknown_collection_result: bool = False,
    ) -> None:
        self.user_id = user_id
        self.collection_key = collection_key
        self.collection_name = collection_name
        self.unknown_collection_result = unknown_collection_result
        self.created_payloads: list[ZoteroItemPayload] = []
        self.created_collections: list[str] = []

    def current_key(self) -> KeyAccess:
        return KeyAccess(user_id=self.user_id, username="tester", can_write=True)

    def list_collections(self, user_id: int) -> list[Collection]:
        assert user_id == self.user_id
        return (
            [Collection(key=self.collection_key, name=self.collection_name)]
            if self.collection_key is not None
            else []
        )

    def create_collection(
        self,
        user_id: int,
        name: str,
        write_token: str,
    ) -> Collection:
        assert user_id == self.user_id
        assert len(write_token) == 32
        self.created_collections.append(name)
        self.collection_key = "NEWCOLL"
        self.collection_name = name
        if self.unknown_collection_result:
            raise ZoteroApiError(status_code=0, detail="Unknown result.")
        return Collection(key="NEWCOLL", name=name)

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
        assert self.collection_key is not None
        return RemoteItem(
            key=item_key,
            item_type="journalArticle",
            title="Example title",
            date="2025",
            first_creator="Smith",
            collections=[self.collection_key],
        )
