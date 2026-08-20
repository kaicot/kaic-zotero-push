"""Durable Zotero batch submission and read-back verification."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, ConfigDict

from kaic_zotero_push.errors import ZoteroApiError
from kaic_zotero_push.models import (
    CreateBatchResponse,
    CreateFailure,
    CreateSuccess,
    ItemOutcome,
    Manifest,
    OutcomeStatus,
    ReferenceRecord,
)
from kaic_zotero_push.parsing import normalize_doi, normalize_title
from kaic_zotero_push.runs import read_model, write_json, write_model
from kaic_zotero_push.zotero.models import RemoteItem, ZoteroItemPayload
from kaic_zotero_push.zotero.responses import (
    extract_create_successes,
    normalize_create_response,
)

if TYPE_CHECKING:
    from pathlib import Path

    from kaic_zotero_push.zotero.gateway import ZoteroGateway

type PayloadPair = tuple[ReferenceRecord, ZoteroItemPayload]


@dataclass(frozen=True, slots=True)
class WriteContext:
    """Immutable dependencies for one approved write."""

    run_dir: Path
    manifest: Manifest
    gateway: ZoteroGateway
    collection_key: str | None


class _BatchState(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    request_sha256: str
    write_token: str


class _BatchKeys(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    request_sha256: str
    successes: list[CreateSuccess]


def verify_record(
    record: ReferenceRecord,
    remote: RemoteItem,
    collection_key: str | None,
) -> bool:
    """Compare sent core metadata with a fetched Zotero item."""
    if record.parsed.item_type != remote.item_type:
        return False
    if normalize_title(record.parsed.title) != normalize_title(remote.title):
        return False
    if record.parsed.doi and normalize_doi(record.parsed.doi) != normalize_doi(remote.doi):
        return False
    return collection_key is None or collection_key in remote.collections


def _batch_state(path: Path, payloads: list[ZoteroItemPayload]) -> _BatchState:
    serializable = [payload.root for payload in payloads]
    canonical = json.dumps(serializable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(canonical.encode()).hexdigest()
    if path.is_file():
        state = read_model(path, _BatchState)
        if state.request_sha256 == request_hash:
            return state
    state = _BatchState(request_sha256=request_hash, write_token=secrets.token_hex(16))
    write_model(path, state)
    return state


def process_batch(
    context: WriteContext,
    batch_number: int,
    batch: list[PayloadPair],
) -> list[ItemOutcome]:
    """Persist, submit, normalize, and verify one batch."""
    records = [pair[0] for pair in batch]
    payloads = [pair[1] for pair in batch]
    batch_dir = context.run_dir / "batches"
    state = _batch_state(batch_dir / f"batch-{batch_number:03d}.state.json", payloads)
    keys_path = batch_dir / f"batch-{batch_number:03d}.keys.json"
    persisted_keys = read_model(keys_path, _BatchKeys) if keys_path.is_file() else None
    persisted_successes = (
        persisted_keys.successes
        if persisted_keys is not None and persisted_keys.request_sha256 == state.request_sha256
        else []
    )
    write_json(
        batch_dir / f"batch-{batch_number:03d}.request.json",
        [payload.root for payload in payloads],
    )
    complete_indices = set(range(len(batch)))
    if {success.index for success in persisted_successes} == complete_indices:
        normalized = CreateBatchResponse(successes=persisted_successes, failures=[])
    else:
        try:
            raw_response = context.gateway.create_items(
                context.manifest.target.user_id,
                payloads,
                state.write_token,
            )
            write_json(
                batch_dir / f"batch-{batch_number:03d}.response.redacted.json",
                raw_response.root,
            )
            known_successes = extract_create_successes(raw_response.root)
            if known_successes:
                write_model(
                    keys_path,
                    _BatchKeys(
                        request_sha256=state.request_sha256,
                        successes=known_successes,
                    ),
                )
            normalized = normalize_create_response(raw_response.root, expected_count=len(batch))
        except ZoteroApiError as error:
            if not persisted_successes:
                return [
                    ItemOutcome(
                        source_index=record.source.source_index,
                        status=OutcomeStatus.WRITE_FAILED,
                        detail=str(error),
                    )
                    for record in records
                ]
            persisted_indices = {success.index for success in persisted_successes}
            normalized = CreateBatchResponse(
                successes=persisted_successes,
                failures=[
                    CreateFailure(index=index, code=500, message=str(error))
                    for index in sorted(complete_indices - persisted_indices)
                ],
            )
    outcomes = [
        ItemOutcome(
            source_index=records[failure.index].source.source_index,
            status=OutcomeStatus.WRITE_FAILED,
            detail=f"{failure.code}: {failure.message}",
        )
        for failure in normalized.failures
    ]
    for success in normalized.successes:
        record = records[success.index]
        try:
            remote = context.gateway.get_item(
                context.manifest.target.user_id,
                success.key,
            )
            verified = verify_record(
                record,
                remote,
                context.collection_key,
            )
        except ZoteroApiError:
            verified = False
        outcomes.append(
            ItemOutcome(
                source_index=record.source.source_index,
                status=(
                    OutcomeStatus.CREATED_VERIFIED if verified else OutcomeStatus.CREATED_UNVERIFIED
                ),
                zotero_key=success.key,
            )
        )
    return outcomes
