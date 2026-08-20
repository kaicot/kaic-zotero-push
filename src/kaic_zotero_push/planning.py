"""No-write extraction, parsing, deduplication, and preview planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kaic_zotero_push.dedup import classify_duplicates
from kaic_zotero_push.errors import CollectionError, RunStateError, ZoteroApiError
from kaic_zotero_push.extractors import extract_document
from kaic_zotero_push.models import Manifest, TargetLibrary
from kaic_zotero_push.parsing import parse_candidate
from kaic_zotero_push.runs import (
    create_run_directory,
    render_preview,
    write_json,
    write_model,
    write_text,
)

if TYPE_CHECKING:
    from pathlib import Path

    from kaic_zotero_push.zotero.gateway import ZoteroGateway
    from kaic_zotero_push.zotero.models import Collection


@dataclass(frozen=True, slots=True)
class PreviewRequest:
    """Preview inputs grouped as one domain request."""

    input_path: Path
    runs_dir: Path
    offline: bool
    collection_name: str | None = None


@dataclass(frozen=True, slots=True)
class PreparedRun:
    """Created preview artifact bundle."""

    run_dir: Path
    manifest: Manifest
    preview: str


def _resolve_collection(name: str | None, collections: list[Collection]) -> Collection | None:
    if name is None:
        return None
    matches = [collection for collection in collections if collection.name == name]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        return None
    keys = ", ".join(collection.key for collection in matches)
    raise CollectionError(detail=f"Collection name is ambiguous; choose a key: {keys}")


def prepare_run(
    request: PreviewRequest,
    gateway: ZoteroGateway | None = None,
) -> PreparedRun:
    """Extract, parse, deduplicate, and persist a no-write preview."""
    extracted = extract_document(request.input_path)
    records = [
        parse_candidate(
            candidate.raw_text,
            source_index=candidate.source_index,
            source_locator=candidate.source_locator,
            structured=candidate.structured,
            section_confirmed=candidate.section_confirmed,
        )
        for candidate in extracted.candidates
    ]
    if request.offline:
        target = TargetLibrary(user_id=0)
    else:
        if gateway is None:
            raise RunStateError(detail="Online preview requires a Zotero gateway.")
        access = gateway.current_key()
        if not access.can_write:
            raise ZoteroApiError(
                status_code=403,
                detail="Personal library write access is required.",
            )
        collection = _resolve_collection(
            request.collection_name,
            gateway.list_collections(access.user_id),
        )
        target = TargetLibrary(
            user_id=access.user_id,
            collection_key=collection.key if collection else None,
            collection_name=collection.name if collection else request.collection_name,
            create_collection=collection is None and request.collection_name is not None,
        )
        records = classify_duplicates(records, gateway.list_existing_items(access.user_id))
    manifest = Manifest.build(
        input_path=request.input_path,
        input_sha256=extracted.file_sha256,
        target=target,
        records=records,
    )
    run_dir = create_run_directory(request.runs_dir)
    preview = render_preview(manifest)
    write_model(run_dir / "extracted.json", extracted)
    write_model(run_dir / "manifest.json", manifest)
    write_text(run_dir / "preview.md", preview)
    write_json(
        run_dir / "run.json",
        {
            "schema_version": "run-v1",
            "state": "awaiting_approval",
            "manifest_sha256": manifest.content_sha256(),
        },
    )
    return PreparedRun(run_dir=run_dir, manifest=manifest, preview=preview)
