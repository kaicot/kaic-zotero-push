"""Approved Zotero writes, verification, receipts, and resume."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kaic_zotero_push.approval import verify_approval
from kaic_zotero_push.batch_writer import (
    PayloadPair,
    WriteContext,
    process_batch,
    recover_batch_outcomes,
    verify_record,
)
from kaic_zotero_push.collection_writer import resolve_collection_key
from kaic_zotero_push.dedup import classify_duplicates
from kaic_zotero_push.destinations import describe_target
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


def _load_previous_outcomes(context: WriteContext) -> list[ItemOutcome]:
    receipt_path = context.run_dir / "receipt.json"
    previous: list[ItemOutcome] = []
    if receipt_path.is_file():
        receipt = read_model(receipt_path, Receipt)
        if receipt.manifest_sha256 != context.manifest.content_sha256():
            raise RunStateError(detail="Receipt does not belong to the approved manifest.")
        previous = receipt.outcomes
    records = {record.source.source_index: record for record in context.manifest.records}
    if len({item.source_index for item in previous}) != len(previous):
        raise RunStateError(detail="Receipt contains duplicate source indices.")
    if any(item.source_index not in records for item in previous):
        raise RunStateError(detail="Receipt contains an unknown source index.")
    finished = {
        item.source_index
        for item in previous
        if item.status
        in {
            OutcomeStatus.CREATED_VERIFIED,
            OutcomeStatus.DUPLICATE_SKIPPED,
            OutcomeStatus.NEEDS_REVIEW,
            OutcomeStatus.PARSE_FAILED,
        }
    }
    if finished != set(records):
        combined = {item.source_index: item for item in previous}
        for item in recover_batch_outcomes(
            context, receipt_covers_all=len(previous) == len(records)
        ):
            if item.source_index not in finished:
                combined[item.source_index] = item
        previous = list(combined.values())
    return previous


def _resume_outcomes(context: WriteContext) -> list[ItemOutcome]:
    previous = _load_previous_outcomes(context)
    records = {record.source.source_index: record for record in context.manifest.records}
    preserved: list[ItemOutcome] = []
    for outcome in previous:
        if outcome.status is OutcomeStatus.NOT_ATTEMPTED or (
            outcome.status is OutcomeStatus.WRITE_FAILED and outcome.retryable is True
        ):
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
                    context.collection_key,
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
    return _reconcile_held_outcomes(context, preserved)


def _reconcile_held_outcomes(
    context: WriteContext,
    outcomes: list[ItemOutcome],
) -> list[ItemOutcome]:
    held = [
        item
        for item in outcomes
        if item.status is OutcomeStatus.WRITE_FAILED
        and item.retryable is not True
        and item.zotero_key is None
    ]
    if not held:
        return outcomes
    existing = context.gateway.list_existing_items(context.manifest.target.user_id)
    records = {record.source.source_index: record for record in context.manifest.records}
    updates: dict[int, ItemOutcome] = {}
    for item in held:
        match = classify_duplicates(
            [records[item.source_index]], existing, target_collection_key=context.collection_key
        )[0]
        key = match.duplicate.matched_item_key
        if match.duplicate.status == "exact" and key is not None:
            remote = context.gateway.get_item(context.manifest.target.user_id, key)
            if verify_record(records[item.source_index], remote, context.collection_key):
                detail = f"Remote match {key} verified; ownership unknown. Held for reconciliation."
            else:
                detail = f"Remote candidate {key} failed read-back comparison; held for review."
        else:
            detail = "No exact destination match; creation remains unproven; retry held."
        cause = (item.detail or "Unresolved submission").split(" | Reconciliation:")[0]
        updates[item.source_index] = item.model_copy(
            update={"detail": f"{cause} | Reconciliation: {detail}"}
        )
    return [updates.get(item.source_index, item) for item in outcomes]


def _validate_user(manifest: Manifest, gateway: ZoteroGateway) -> None:
    access = gateway.current_key()
    if not access.can_write or access.user_id != manifest.target.user_id:
        raise ZoteroApiError(status_code=403, detail="Approval targets a different writable user.")


def _completed_receipt(run_dir: Path, manifest: Manifest) -> Receipt | None:
    path = run_dir / "receipt.json"
    if not path.is_file():
        return None
    receipt = read_model(path, Receipt)
    if receipt.manifest_sha256 != manifest.content_sha256():
        raise RunStateError(detail="Receipt does not belong to the approved manifest.")
    expected = {record.source.source_index for record in manifest.records}
    actual = {item.source_index for item in receipt.outcomes}
    final_states = {
        OutcomeStatus.CREATED_VERIFIED,
        OutcomeStatus.DUPLICATE_SKIPPED,
        OutcomeStatus.NEEDS_REVIEW,
        OutcomeStatus.PARSE_FAILED,
    }
    if (
        actual == expected
        and len(receipt.outcomes) == len(expected)
        and all(item.status in final_states for item in receipt.outcomes)
    ):
        return receipt
    return None


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
    if not create_records:
        return [], []
    refreshed = classify_duplicates(
        create_records,
        context.gateway.list_existing_items(context.manifest.target.user_id),
        target_collection_key=context.collection_key,
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
                    status=OutcomeStatus(record.decision.value),
                    detail=" / ".join(
                        (
                            "Duplicate recheck",
                            record.duplicate.reason or "unknown",
                            record.duplicate.matched_item_key or "unknown",
                        )
                    ),
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
        collection_key=context.collection_key,
        destination=describe_target(context.manifest.target, context.collection_key),
    )
    write_model(context.run_dir / "receipt.json", receipt)
    is_complete = all(
        outcome.status
        not in {
            OutcomeStatus.CREATED_UNVERIFIED,
            OutcomeStatus.WRITE_FAILED,
            OutcomeStatus.NOT_ATTEMPTED,
        }
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
    completed = _completed_receipt(request.run_dir, manifest)
    if completed is not None:
        return completed
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
    batch_numbers = [
        int(path.name.split(".")[0].removeprefix("batch-"))
        for path in (context.run_dir / "batches").glob("batch-*.state.json")
    ]
    batches = partition_batches(pairs)
    start = max(batch_numbers, default=0) + 1
    for offset, batch in enumerate(batches):
        batch_outcomes = process_batch(context, start + offset, batch)
        outcomes.extend(batch_outcomes)
        if any(item.status is OutcomeStatus.WRITE_FAILED for item in batch_outcomes):
            outcomes.extend(
                ItemOutcome(
                    source_index=record.source.source_index,
                    status=OutcomeStatus.NOT_ATTEMPTED,
                    detail="Stopped after a batch failure; resume this run.",
                )
                for later in batches[offset + 1 :]
                for record, _ in later
            )
            break
    return _persist_receipt(context, outcomes)
