"""Durable Zotero batch submission and read-back verification."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, ConfigDict

from kaic_zotero_push.errors import RunStateError, ZoteroApiError
from kaic_zotero_push.models import (
    CreateBatchResponse,
    CreateFailure,
    CreateSuccess,
    ItemOutcome,
    Manifest,
    OutcomeStatus,
    Receipt,
    ReferenceRecord,
)
from kaic_zotero_push.parsing import normalize_doi, normalize_title
from kaic_zotero_push.runs import read_model, write_json, write_model
from kaic_zotero_push.zotero.models import RemoteItem, ZoteroItemPayload, ZoteroResponsePayload
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
    manifest_sha256: str | None = None
    source_indices: list[int] | None = None
    submitted: bool = False


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
    return (
        not remote.collections if collection_key is None else collection_key in remote.collections
    )


def _batch_state(
    path: Path,
    payloads: list[ZoteroItemPayload],
    context: WriteContext,
    records: list[ReferenceRecord],
) -> _BatchState:
    serializable = [payload.root for payload in payloads]
    canonical = json.dumps(serializable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(canonical.encode()).hexdigest()
    if path.is_file():
        raise RunStateError(detail="Batch journal already exists; resume the original run.")
    state = _BatchState(
        request_sha256=request_hash,
        write_token=secrets.token_hex(16),
        manifest_sha256=context.manifest.content_sha256(),
        source_indices=[record.source.source_index for record in records],
    )
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
    state_path = batch_dir / f"batch-{batch_number:03d}.state.json"
    state = _batch_state(state_path, payloads, context, records)
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
            write_model(state_path, state.model_copy(update={"submitted": True}))
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
                outcomes = [
                    ItemOutcome(
                        source_index=record.source.source_index,
                        status=OutcomeStatus.WRITE_FAILED,
                        detail=str(error),
                        retryable=_retryable_failure(error.status_code),
                    )
                    for record in records
                ]
                write_model(
                    batch_dir / f"batch-{batch_number:03d}.outcomes.json",
                    Receipt(manifest_sha256=context.manifest.content_sha256(), outcomes=outcomes),
                )
                return outcomes
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
            retryable=_retryable_failure(failure.code),
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
    write_model(
        batch_dir / f"batch-{batch_number:03d}.outcomes.json",
        Receipt(manifest_sha256=context.manifest.content_sha256(), outcomes=outcomes),
    )
    return outcomes


def _retryable_failure(code: int) -> bool:
    # Permission failures are definite non-creations; commit revalidates identity/access.
    # Invalid payloads require a new preview. Locked/rate-limited/unknown results need
    # reconciliation, not a new token with the same failing request.
    return code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}


def _recover_one_batch(context: WriteContext, path: Path) -> list[ItemOutcome]:
    recovered: dict[int, ItemOutcome] = {}
    state = read_model(path, _BatchState)
    indices = _validate_batch_mapping(context, state)
    stem = path.name.removesuffix(".state.json")
    for index in indices:
        recovered[index] = ItemOutcome(
            source_index=index,
            status=OutcomeStatus.WRITE_FAILED,
            retryable=not state.submitted,
            detail=(
                "Submission outcome unknown; reconcile this run before retry."
                if state.submitted
                else "Batch was not submitted."
            ),
        )
    outcome_path = path.with_name(f"{stem}.outcomes.json")
    response_path = path.with_name(f"{stem}.response.redacted.json")
    if not outcome_path.is_file() and response_path.is_file():
        recovered.update(_recover_response(response_path, indices))
    if outcome_path.is_file():
        recovered.update(_batch_outcomes(outcome_path, state.manifest_sha256, indices))
    keys_path = path.with_name(f"{stem}.keys.json")
    if keys_path.is_file():
        keys = read_model(keys_path, _BatchKeys)
        if keys.request_sha256 != state.request_sha256:
            raise RunStateError(detail="Persisted keys do not match the batch request.")
        for success in keys.successes:
            if success.index >= len(indices):
                raise RunStateError(detail="Persisted success index is outside the request.")
            index = indices[success.index]
            recovered[index] = ItemOutcome(
                source_index=index,
                status=OutcomeStatus.CREATED_UNVERIFIED,
                zotero_key=success.key,
            )
    return list(recovered.values())


def _batch_outcomes(
    path: Path, manifest_hash: str | None, indices: list[int]
) -> dict[int, ItemOutcome]:
    receipt = read_model(path, Receipt)
    if receipt.manifest_sha256 != manifest_hash:
        raise RunStateError(detail="Batch outcomes do not match the manifest.")
    if any(item.source_index not in indices for item in receipt.outcomes):
        raise RunStateError(detail="Batch outcome source is not in the request.")
    return {item.source_index: item for item in receipt.outcomes}


def _recover_response(path: Path, indices: list[int]) -> dict[int, ItemOutcome]:
    response = read_model(path, ZoteroResponsePayload)
    try:
        normalized = normalize_create_response(response.root, expected_count=len(indices))
    except ZoteroApiError:
        return {}
    if any(item.index >= len(indices) for item in [*normalized.successes, *normalized.failures]):
        raise RunStateError(detail="Stored response index is outside the request.")
    recovered = {
        indices[item.index]: ItemOutcome(
            source_index=indices[item.index],
            status=OutcomeStatus.WRITE_FAILED,
            detail=f"{item.code}: {item.message}",
            retryable=_retryable_failure(item.code),
        )
        for item in normalized.failures
    }
    recovered.update(
        {
            indices[item.index]: ItemOutcome(
                source_index=indices[item.index],
                status=OutcomeStatus.CREATED_UNVERIFIED,
                zotero_key=item.key,
            )
            for item in normalized.successes
        }
    )
    return recovered


def _validate_batch_mapping(context: WriteContext, state: _BatchState) -> list[int]:
    if state.manifest_sha256 is None or state.source_indices is None:
        raise RunStateError(
            detail="Legacy batch needs reconciliation before resume; do not start a new import."
        )
    if state.manifest_sha256 != context.manifest.content_sha256():
        raise RunStateError(detail="Batch journal belongs to a different manifest.")
    indices = state.source_indices
    records = {record.source.source_index for record in context.manifest.records}
    if len(indices) != len(set(indices)) or any(index not in records for index in indices):
        raise RunStateError(detail="Batch source mapping is invalid.")
    return indices


def recover_batch_outcomes(
    context: WriteContext,
    *,
    receipt_covers_all: bool = False,
) -> list[ItemOutcome]:
    """Recover source-bound successes before duplicate lookup or any new submission."""
    recovered: dict[int, ItemOutcome] = {}
    for path in sorted((context.run_dir / "batches").glob("batch-*.state.json")):
        state = read_model(path, _BatchState)
        if receipt_covers_all and state.source_indices is None:
            continue
        recovered.update({item.source_index: item for item in _recover_one_batch(context, path)})
    return list(recovered.values())
