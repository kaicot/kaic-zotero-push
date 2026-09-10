"""Approval creation and validation."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import override

from kaic_zotero_push.errors import KaicZoteroPushError, RunStateError
from kaic_zotero_push.models import Approval, Manifest


@dataclass(frozen=True, slots=True)
class ApprovalMismatchError(KaicZoteroPushError):
    """Persisted approval does not match the current manifest."""

    expected: str
    actual: str

    @override
    def __str__(self) -> str:
        """Return a redacted approval error."""
        return "Approval is invalid because the input, manifest, library, or collection changed."


def approve_manifest(manifest: Manifest) -> Approval:
    """Create an approval for an already presented manifest."""
    if manifest.target.user_id == 0:
        raise RunStateError(detail="Offline previews cannot be approved for writing.")
    verify_input(manifest)
    return Approval(binding_sha256=manifest.approval_binding())


def verify_input(manifest: Manifest) -> None:
    """Bind writes to the current bytes of the previewed source document."""
    try:
        with Path(manifest.input_path).open("rb") as source:
            actual = hashlib.file_digest(source, "sha256").hexdigest()
    except OSError as error:
        raise RunStateError(
            detail="Source document is unavailable; restore it or create a new preview."
        ) from error
    if actual != manifest.input_sha256:
        raise RunStateError(
            detail="Source document changed; create a new preview and obtain approval."
        )


def verify_approval(manifest: Manifest, approval: Approval) -> None:
    """Require approval to match every bound component."""
    expected = manifest.approval_binding()
    if approval.binding_sha256 != expected:
        raise ApprovalMismatchError(expected=expected, actual=approval.binding_sha256)
    if manifest.target.user_id == 0:
        raise RunStateError(detail="Offline previews cannot be committed.")
    verify_input(manifest)
