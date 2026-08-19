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
    ItemOutcome,
    Manifest,
    OutcomeStatus,
    ReferenceRecord,
)
from kaic_zotero_push.parsing import normalize_doi, normalize_title
from kaic_zotero_push.runs import read_model, write_json, write_model
from kaic_zotero_push.zotero.models import RemoteItem, ZoteroItemPayload
from kaic_zotero_push.zotero.responses import normalize_create_response

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


class _BatchState(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    request_sha256: str
    write_token: str


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
    write_json(
        batch_dir / f"batch-{batch_number:03d}.request.json",
        [payload.root for payload in payloads],
    )
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
        normalized = normalize_create_response(raw_response.root, expected_count=len(batch))
    except ZoteroApiError as error:
        return [
            ItemOutcome(
                source_index=record.source.source_index,
                status=OutcomeStatus.WRITE_FAILED,
                detail=str(error),
            )
            for record in records
        ]
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
                context.manifest.target.collection_key,
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
