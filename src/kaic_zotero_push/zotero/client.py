"""Synchronous Zotero Web API v3 client with redacted errors."""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING, Final, Literal, Self, final

import httpx2
from pydantic import TypeAdapter, ValidationError

from kaic_zotero_push.errors import ZoteroApiError
from kaic_zotero_push.models import Creator, ExistingItem, JsonValue, ParsedReference
from kaic_zotero_push.zotero.models import (
    ApiItemEnvelope,
    Collection,
    CollectionEnvelope,
    CurrentKeyResponse,
    KeyAccess,
    RemoteItem,
    ZoteroItemPayload,
    ZoteroResponsePayload,
)

if TYPE_CHECKING:
    from types import TracebackType

_LIMITS = httpx2.Limits(
    max_connections=200,
    max_keepalive_connections=40,
    keepalive_expiry=30.0,
)
_TIMEOUT = httpx2.Timeout(connect=5.0, read=30.0, write=10.0, pool=10.0)
_SOCKET_OPTIONS = [(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)]
_PAGE_SIZE: Final = 100
_MAX_BATCH_SIZE: Final = 50


@final
class ZoteroClient:
    """Owned HTTP clients for Zotero reads and non-retried writes."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.zotero.org",
        transport: httpx2.BaseTransport | None = None,
    ) -> None:
        """Create read and non-retried write clients."""
        headers = {
            "Zotero-API-Key": api_key,
            "Zotero-API-Version": "3",
            "Content-Type": "application/json",
            "User-Agent": "kaic-zotero-push/0.1.1",
        }
        if transport is not None:
            self._read_client = httpx2.Client(
                base_url=base_url,
                headers=headers,
                timeout=_TIMEOUT,
                follow_redirects=True,
                transport=transport,
            )
            self._write_client = self._read_client
        else:
            read_transport = httpx2.HTTPTransport(
                http2=True,
                retries=3,
                limits=_LIMITS,
                socket_options=_SOCKET_OPTIONS,
            )
            write_transport = httpx2.HTTPTransport(
                http2=True,
                retries=0,
                limits=_LIMITS,
                socket_options=_SOCKET_OPTIONS,
            )
            self._read_client = httpx2.Client(
                base_url=base_url,
                headers=headers,
                timeout=_TIMEOUT,
                follow_redirects=True,
                transport=read_transport,
            )
            self._write_client = httpx2.Client(
                base_url=base_url,
                headers=headers,
                timeout=_TIMEOUT,
                follow_redirects=True,
                transport=write_transport,
            )

    def __enter__(self) -> Self:
        """Return this owned client."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close clients when leaving a context."""
        self.close()

    def close(self) -> None:
        """Close owned transports."""
        self._read_client.close()
        if self._write_client is not self._read_client:
            self._write_client.close()

    @staticmethod
    def _check(response: httpx2.Response) -> None:
        if response.is_success:
            return
        detail = response.text[:300] or "Request failed."
        raise ZoteroApiError(status_code=response.status_code, detail=detail)

    def current_key(self) -> KeyAccess:
        """Verify key identity and personal-library access."""
        try:
            response = self._read_client.get("/keys/current")
            self._check(response)
            raw = CurrentKeyResponse.model_validate_json(response.content)
        except (httpx2.RequestError, ValidationError) as error:
            raise ZoteroApiError(
                status_code=0,
                detail="Could not verify the Zotero API key.",
            ) from error
        return KeyAccess(
            user_id=raw.user_id,
            username=raw.username,
            can_write=raw.access.user.library,
        )

    def list_collections(self, user_id: int) -> list[Collection]:
        """List personal-library collections."""
        response = self._read_client.get(
            f"/users/{user_id}/collections",
            params={"limit": _PAGE_SIZE},
        )
        self._check(response)
        envelopes = TypeAdapter(list[CollectionEnvelope]).validate_json(response.content)
        return [
            Collection(
                key=envelope.key,
                name=envelope.data.name,
                parent_key=self._parent_key(envelope.data.parent_collection),
            )
            for envelope in envelopes
        ]

    @staticmethod
    def _parent_key(value: str | Literal[False]) -> str | None:
        return value or None

    def list_existing_items(self, user_id: int) -> list[ExistingItem]:
        """Build a duplicate index from all top-level personal items."""
        items: list[ExistingItem] = []
        start = 0
        while True:
            response = self._read_client.get(
                f"/users/{user_id}/items/top",
                params={"format": "json", "limit": _PAGE_SIZE, "start": start},
            )
            self._check(response)
            page = TypeAdapter(list[ApiItemEnvelope]).validate_json(response.content)
            items.extend(self._existing_item(item) for item in page)
            if len(page) < _PAGE_SIZE:
                return items
            start += len(page)

    @staticmethod
    def _existing_item(item: ApiItemEnvelope) -> ExistingItem:
        creators = [
            Creator(
                creator_type=creator.creator_type,
                first_name=creator.first_name,
                last_name=creator.last_name,
                name=creator.name,
            )
            for creator in item.data.creators
        ]
        return ExistingItem(
            key=item.key,
            parsed=ParsedReference(
                item_type=item.data.item_type,
                title=item.data.title,
                creators=creators,
                date=item.data.date,
                container_title=item.data.publication_title or item.data.book_title,
                doi=item.data.doi,
                isbn=item.data.isbn,
                url=item.data.url,
            ),
        )

    def get_template(self, item_type: str) -> ZoteroItemPayload:
        """Fetch the current editable template for an item type."""
        response = self._read_client.get("/items/new", params={"itemType": item_type})
        self._check(response)
        return ZoteroItemPayload.model_validate_json(response.content)

    def create_items(
        self,
        user_id: int,
        items: list[ZoteroItemPayload],
        write_token: str,
    ) -> ZoteroResponsePayload:
        """Create at most 50 metadata-only items without transport retries."""
        if not 1 <= len(items) <= _MAX_BATCH_SIZE:
            raise ZoteroApiError(status_code=413, detail="Create requests require 1 to 50 items.")
        try:
            response = self._write_client.post(
                f"/users/{user_id}/items",
                headers={"Zotero-Write-Token": write_token},
                content=TypeAdapter(list[dict[str, JsonValue]]).dump_json(
                    [payload.root for payload in items]
                ),
            )
        except httpx2.RequestError as error:
            raise ZoteroApiError(
                status_code=0,
                detail="Zotero write outcome is unknown.",
            ) from error
        self._check(response)
        return ZoteroResponsePayload.model_validate_json(response.content)

    def get_item(self, user_id: int, item_key: str) -> RemoteItem:
        """Fetch one item for post-write verification."""
        response = self._read_client.get(f"/users/{user_id}/items/{item_key}")
        self._check(response)
        item = ApiItemEnvelope.model_validate_json(response.content)
        first_creator = item.data.creators[0].last_name if item.data.creators else ""
        return RemoteItem(
            key=item.key,
            item_type=item.data.item_type,
            title=item.data.title,
            doi=item.data.doi,
            date=item.data.date,
            first_creator=first_creator or "",
            collections=item.data.collections,
        )
