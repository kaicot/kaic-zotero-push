"""Approved collection resolution and durable create-if-missing state."""

from __future__ import annotations

import secrets
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, ConfigDict

from kaic_zotero_push.errors import CollectionError, RunStateError, ZoteroApiError
from kaic_zotero_push.runs import read_model, write_model

if TYPE_CHECKING:
    from pathlib import Path

    from kaic_zotero_push.models import Manifest
    from kaic_zotero_push.zotero.gateway import ZoteroGateway
    from kaic_zotero_push.zotero.models import Collection


class _CollectionState(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    manifest_sha256: str
    name: str
    write_token: str
    key: str | None = None


def _matching_root_collections(
    collections: list[Collection],
    name: str,
) -> list[Collection]:
    return [
        collection
        for collection in collections
        if collection.name == name and collection.parent_key is None
    ]


def _load_collection_state(
    state_path: Path,
    manifest: Manifest,
    name: str,
) -> _CollectionState:
    manifest_sha256 = manifest.content_sha256()
    state = (
        read_model(state_path, _CollectionState)
        if state_path.is_file()
        else _CollectionState(
            manifest_sha256=manifest_sha256,
            name=name,
            write_token=secrets.token_hex(16),
        )
    )
    if state.manifest_sha256 != manifest_sha256 or state.name != name:
        raise RunStateError(detail="Collection state does not belong to the approved manifest.")
    write_model(state_path, state)
    return state


def _create_or_reconcile(
    gateway: ZoteroGateway,
    user_id: int,
    state: _CollectionState,
) -> Collection:
    matches = _matching_root_collections(gateway.list_collections(user_id), state.name)
    if len(matches) > 1:
        raise CollectionError(detail="Collection name is ambiguous at the library root.")
    if matches:
        return matches[0]
    try:
        return gateway.create_collection(user_id, state.name, state.write_token)
    except ZoteroApiError as error:
        if error.status_code != 0:
            raise
        reconciled = _matching_root_collections(
            gateway.list_collections(user_id),
            state.name,
        )
        if len(reconciled) != 1:
            raise
        return reconciled[0]


def resolve_collection_key(
    run_dir: Path,
    manifest: Manifest,
    gateway: ZoteroGateway,
) -> str | None:
    """Resolve or create only the collection destination bound by approval."""
    target = manifest.target
    collections = gateway.list_collections(target.user_id)
    if target.collection_key is not None:
        if target.collection_key not in {collection.key for collection in collections}:
            raise CollectionError(detail="The approved collection no longer exists.")
        return target.collection_key
    if not target.create_collection:
        return None
    if target.collection_name is None:
        raise RunStateError(detail="Approved collection creation has no collection name.")
    state_path = run_dir / "collection.state.json"
    state = _load_collection_state(state_path, manifest, target.collection_name)
    if state.key is not None:
        if state.key not in {collection.key for collection in collections}:
            raise CollectionError(detail="The created collection no longer exists.")
        return state.key
    created = _create_or_reconcile(gateway, target.user_id, state)
    write_model(state_path, state.model_copy(update={"key": created.key}))
    return created.key
