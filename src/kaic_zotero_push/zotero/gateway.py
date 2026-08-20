"""Zotero gateway protocol used by the deterministic pipeline."""

from typing import Protocol

from kaic_zotero_push.models import ExistingItem
from kaic_zotero_push.zotero.models import (
    Collection,
    KeyAccess,
    RemoteItem,
    ZoteroItemPayload,
    ZoteroResponsePayload,
)


class ZoteroGateway(Protocol):
    """Required personal-library Zotero operations."""

    def current_key(self) -> KeyAccess:
        """Return key identity and personal-library write access."""
        ...

    def list_collections(self, user_id: int) -> list[Collection]:
        """Return personal-library collections."""
        ...

    def create_collection(
        self,
        user_id: int,
        name: str,
        write_token: str,
    ) -> Collection:
        """Create one approved root collection."""
        ...

    def list_existing_items(self, user_id: int) -> list[ExistingItem]:
        """Return top-level items used for duplicate detection."""
        ...

    def get_template(self, item_type: str) -> ZoteroItemPayload:
        """Return the live editable template for one item type."""
        ...

    def create_items(
        self,
        user_id: int,
        items: list[ZoteroItemPayload],
        write_token: str,
    ) -> ZoteroResponsePayload:
        """Create one metadata-only batch."""
        ...

    def get_item(self, user_id: int, item_key: str) -> RemoteItem:
        """Return one item for read-back verification."""
        ...
