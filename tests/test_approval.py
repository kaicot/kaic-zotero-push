from pathlib import Path

import pytest

from kaic_zotero_push.approval import ApprovalMismatchError, approve_manifest, verify_approval
from kaic_zotero_push.models import Manifest, TargetLibrary
from kaic_zotero_push.parsing import parse_candidate


def _manifest(collection_key: str | None = "COLL1") -> Manifest:
    return Manifest.build(
        input_path=Path("references.txt"),
        input_sha256="a" * 64,
        target=TargetLibrary(user_id=123, collection_key=collection_key),
        records=[
            parse_candidate(
                "Smith, J. (2025). Example title. Journal.",
                source_index=1,
                source_locator="line=1",
            )
        ],
    )


def test_verify_approval_when_manifest_is_unchanged() -> None:
    # Given
    manifest = _manifest()
    approval = approve_manifest(manifest)

    # When
    verify_approval(manifest, approval)

    # Then
    assert approval.binding_sha256 == manifest.approval_binding()


def test_verify_approval_when_collection_changes() -> None:
    # Given
    approval = approve_manifest(_manifest())
    changed = _manifest(collection_key="OTHER")

    # When / Then
    with pytest.raises(ApprovalMismatchError):
        verify_approval(changed, approval)
