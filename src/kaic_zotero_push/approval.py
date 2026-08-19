"""Approval creation and validation."""

from dataclasses import dataclass
from typing import override

from kaic_zotero_push.models import Approval, Manifest


@dataclass(frozen=True, slots=True)
class ApprovalMismatchError(Exception):
    """Persisted approval does not match the current manifest."""

    expected: str
    actual: str

    @override
    def __str__(self) -> str:
        """Return a redacted approval error."""
        return "Approval is invalid because the input, manifest, library, or collection changed."


def approve_manifest(manifest: Manifest) -> Approval:
    """Create an approval for an already presented manifest."""
    return Approval(binding_sha256=manifest.approval_binding())


def verify_approval(manifest: Manifest, approval: Approval) -> None:
    """Require approval to match every bound component."""
    expected = manifest.approval_binding()
    if approval.binding_sha256 != expected:
        raise ApprovalMismatchError(expected=expected, actual=approval.binding_sha256)
