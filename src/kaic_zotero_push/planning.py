"""No-write extraction, parsing, deduplication, and preview planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from kaic_zotero_push.dedup import classify_duplicates
from kaic_zotero_push.destinations import collection_path, resolve_collection
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


@dataclass(frozen=True, slots=True)
class PreviewRequest:
    """Preview inputs grouped as one domain request."""

    input_path: Path
    runs_dir: Path
    offline: bool
    collection_name: str | None = None
    collection_key: str | None = None
    library_root: bool = False
    proposed_collection: bool = False

    def validate_destination(self) -> None:
        """Reject missing or conflicting destinations before credentials or I/O."""
        for value in (self.collection_name, self.collection_key):
            if value is not None and not value.strip():
                raise CollectionError(detail="Collection name/key cannot be blank.")
        count = sum(
            (self.collection_name is not None, self.collection_key is not None, self.library_root)
        )
        if self.offline:
            if count or self.proposed_collection:
                raise CollectionError(
                    detail="--offline does not bind a destination; omit destination options."
                )
        elif count != 1:
            raise CollectionError(
                detail="Choose one: --collection NAME, --collection-key KEY, or --library-root."
            )
        if self.proposed_collection and self.collection_name is None:
            raise CollectionError(detail="--proposed-collection requires --collection NAME.")


@dataclass(frozen=True, slots=True)
class PreparedRun:
    """Created preview artifact bundle."""

    run_dir: Path
    manifest: Manifest
    preview: str


def prepare_run(
    request: PreviewRequest,
    gateway: ZoteroGateway | None = None,
) -> PreparedRun:
    """Extract, parse, deduplicate, and persist a no-write preview."""
    request.validate_destination()
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
        records = classify_duplicates(records, [])
    else:
        if gateway is None:
            raise RunStateError(detail="Online preview requires a Zotero gateway.")
        access = gateway.current_key()
        if not access.can_write:
            raise ZoteroApiError(
                status_code=403,
                detail="Personal library write access is required.",
            )
        collections = gateway.list_collections(access.user_id)
        collection = resolve_collection(
            request.collection_name,
            request.collection_key,
            collections,
        )
        target = TargetLibrary(
            user_id=access.user_id,
            collection_key=collection.key if collection else None,
            collection_name=collection.name if collection else request.collection_name,
            create_collection=collection is None and request.collection_name is not None,
            collection_path=collection_path(collection, collections) if collection else None,
            proposed_collection=True if request.proposed_collection else None,
        )
        records = classify_duplicates(
            records,
            gateway.list_existing_items(access.user_id),
            target_collection_key=target.collection_key,
            target_is_new_collection=target.create_collection,
        )
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
