"""Approved Zotero writes, verification, receipts, and resume."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kaic_zotero_push.approval import verify_approval
from kaic_zotero_push.batch_writer import (
    PayloadPair,
    WriteContext,
    process_batch,
    verify_record,
)
from kaic_zotero_push.collection_writer import resolve_collection_key
from kaic_zotero_push.dedup import classify_duplicates
from kaic_zotero_push.errors import RunStateError, ZoteroApiError
from kaic_zotero_push.models import (
    Approval,
    Decision,
    ItemOutcome,
    Manifest,
    OutcomeStatus,
    Receipt,
    ReferenceRecord,
)
from kaic_zotero_push.runs import read_model, write_json, write_model
from kaic_zotero_push.zotero.mapper import map_record
from kaic_zotero_push.zotero.responses import partition_batches

if TYPE_CHECKING:
    from pathlib import Path

    from kaic_zotero_push.zotero.gateway import ZoteroGateway
    from kaic_zotero_push.zotero.models import ZoteroItemPayload


@dataclass(frozen=True, slots=True)
class CommitRequest:
    """Commit inputs grouped as one domain request."""

    run_dir: Path


def _initial_outcomes(manifest: Manifest) -> list[ItemOutcome]:
    mapping = {
        Decision.DUPLICATE_SKIPPED: OutcomeStatus.DUPLICATE_SKIPPED,
        Decision.NEEDS_REVIEW: OutcomeStatus.NEEDS_REVIEW,
        Decision.PARSE_FAILED: OutcomeStatus.PARSE_FAILED,
    }
    return [
        ItemOutcome(source_index=record.source.source_index, status=mapping[record.decision])
        for record in manifest.records
        if record.decision in mapping
    ]


def _resume_outcomes(context: WriteContext) -> list[ItemOutcome]:
    receipt_path = context.run_dir / "receipt.json"
    if not receipt_path.is_file():
        return []
    receipt = read_model(receipt_path, Receipt)
    if receipt.manifest_sha256 != context.manifest.content_sha256():
        raise RunStateError(detail="Receipt does not belong to the approved manifest.")
    records = {record.source.source_index: record for record in context.manifest.records}
    preserved: list[ItemOutcome] = []
    for outcome in receipt.outcomes:
        if outcome.status in {OutcomeStatus.WRITE_FAILED, OutcomeStatus.NOT_ATTEMPTED}:
            continue
        if outcome.status is OutcomeStatus.CREATED_UNVERIFIED and outcome.zotero_key:
            record = records[outcome.source_index]
            try:
                remote = context.gateway.get_item(
                    context.manifest.target.user_id,
                    outcome.zotero_key,
                )
                verified = verify_record(
                    record,
                    remote,
                    context.manifest.target.collection_key,
                )
            except ZoteroApiError:
                verified = False
            preserved.append(
                outcome.model_copy(
                    update={
                        "status": (
                            OutcomeStatus.CREATED_VERIFIED
                            if verified
                            else OutcomeStatus.CREATED_UNVERIFIED
                        )
                    }
                )
            )
        else:
            preserved.append(outcome)
    return preserved


def _validate_user(manifest: Manifest, gateway: ZoteroGateway) -> None:
    access = gateway.current_key()
    if not access.can_write or access.user_id != manifest.target.user_id:
        raise ZoteroApiError(status_code=403, detail="Approval targets a different writable user.")


def _pending_records(
    context: WriteContext,
    completed_indices: set[int],
) -> tuple[list[ReferenceRecord], list[ItemOutcome]]:
    create_records = [
        record
        for record in context.manifest.records
        if record.decision is Decision.CREATE
        and record.source.source_index not in completed_indices
    ]
    refreshed = classify_duplicates(
        create_records,
        context.gateway.list_existing_items(context.manifest.target.user_id),
    )
    pending: list[ReferenceRecord] = []
    duplicates: list[ItemOutcome] = []
    for record in refreshed:
        if record.decision is Decision.CREATE:
            pending.append(record)
        else:
            duplicates.append(
                ItemOutcome(
                    source_index=record.source.source_index,
                    status=OutcomeStatus.DUPLICATE_SKIPPED,
                    detail="A duplicate appeared after approval.",
                )
            )
    return pending, duplicates


def _payload_pairs(context: WriteContext, records: list[ReferenceRecord]) -> list[PayloadPair]:
    template_cache: dict[str, ZoteroItemPayload] = {}
    pairs: list[PayloadPair] = []
    for record in records:
        template = template_cache.get(record.parsed.item_type)
        if template is None:
            template = context.gateway.get_template(record.parsed.item_type)
            template_cache[record.parsed.item_type] = template
        pairs.append(
            (
                record,
                map_record(
                    record,
                    template,
                    collection_key=context.collection_key,
                ),
            )
        )
    return pairs


def _persist_receipt(context: WriteContext, outcomes: list[ItemOutcome]) -> Receipt:
    receipt = Receipt(
        manifest_sha256=context.manifest.content_sha256(),
        outcomes=sorted(outcomes, key=lambda item: item.source_index),
    )
    write_model(context.run_dir / "receipt.json", receipt)
    is_complete = all(
        outcome.status not in {OutcomeStatus.CREATED_UNVERIFIED, OutcomeStatus.WRITE_FAILED}
        for outcome in receipt.outcomes
    )
    write_json(
        context.run_dir / "run.json",
        {
            "schema_version": "run-v1",
            "state": "completed" if is_complete else "partial",
            "manifest_sha256": context.manifest.content_sha256(),
        },
    )
    return receipt


def commit_run(request: CommitRequest, gateway: ZoteroGateway) -> Receipt:
    """Write only an approved plan, then read back every created item."""
    manifest = read_model(request.run_dir / "manifest.json", Manifest)
    approval = read_model(request.run_dir / "approval.json", Approval)
    verify_approval(manifest, approval)
    _validate_user(manifest, gateway)
    collection_key = resolve_collection_key(request.run_dir, manifest, gateway)
    context = WriteContext(
        run_dir=request.run_dir,
        manifest=manifest,
        gateway=gateway,
        collection_key=collection_key,
    )
    outcomes = _resume_outcomes(context)
    completed_indices = {outcome.source_index for outcome in outcomes}
    outcomes.extend(
        outcome
        for outcome in _initial_outcomes(manifest)
        if outcome.source_index not in completed_indices
    )
    pending, duplicate_outcomes = _pending_records(context, completed_indices)
    outcomes.extend(duplicate_outcomes)
    pairs = _payload_pairs(context, pending)
    for batch_number, batch in enumerate(partition_batches(pairs), start=1):
        outcomes.extend(process_batch(context, batch_number, batch))
    return _persist_receipt(context, outcomes)
