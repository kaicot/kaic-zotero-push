"""Typed application errors."""

from dataclasses import dataclass
from typing import override


class KaicZoteroPushError(Exception):
    """Base error for expected user-facing failures."""


@dataclass(frozen=True, slots=True)
class InputError(KaicZoteroPushError):
    """An input document cannot be processed safely."""

    code: str
    detail: str

    @override
    def __str__(self) -> str:
        """Return the public input error."""
        return f"{self.code}: {self.detail}"


@dataclass(frozen=True, slots=True)
class CredentialError(KaicZoteroPushError):
    """Zotero credentials are absent or unusable."""

    detail: str

    @override
    def __str__(self) -> str:
        """Return the redacted credential error."""
        return self.detail


@dataclass(frozen=True, slots=True)
class ZoteroApiError(KaicZoteroPushError):
    """The Zotero API rejected or could not complete a request."""

    status_code: int
    detail: str

    @override
    def __str__(self) -> str:
        """Return the redacted API error."""
        return f"Zotero API {self.status_code}: {self.detail}"


@dataclass(frozen=True, slots=True)
class CollectionError(KaicZoteroPushError):
    """A requested Zotero collection cannot be resolved uniquely."""

    detail: str

    @override
    def __str__(self) -> str:
        """Return the collection resolution error."""
        return self.detail


@dataclass(frozen=True, slots=True)
class RunStateError(KaicZoteroPushError):
    """Persisted run state is missing or inconsistent."""

    detail: str

    @override
    def __str__(self) -> str:
        """Return the run-state error."""
        return self.detail
