"""Immutable domain and boundary models."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar, Final, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_core import PydanticCustomError

if TYPE_CHECKING:
    from pathlib import Path

_YEAR_LENGTH: Final = 4
_COLLECTION_INTENT_ERROR: Final = "collection_intent"
_COLLECTION_INTENT_MESSAGE: Final = "Collection creation requires a name and no existing key."

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]


class StrictModel(BaseModel):
    """Frozen model that rejects undeclared boundary fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")


class ParseStatus(StrEnum):
    """Citation parser disposition."""

    PARSED = "parsed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class Decision(StrEnum):
    """Action selected for a reference record."""

    CREATE = "create"
    DUPLICATE_SKIPPED = "duplicate_skipped"
    NEEDS_REVIEW = "needs_review"
    PARSE_FAILED = "parse_failed"


class OutcomeStatus(StrEnum):
    """Final write result for one reference."""

    CREATED_VERIFIED = "created_verified"
    CREATED_UNVERIFIED = "created_unverified"
    DUPLICATE_SKIPPED = "duplicate_skipped"
    NEEDS_REVIEW = "needs_review"
    PARSE_FAILED = "parse_failed"
    WRITE_FAILED = "write_failed"
    NOT_ATTEMPTED = "not_attempted"


class StructuredReference(StrictModel):
    """Known columns from a spreadsheet-like source."""

    title: str | None = None
    author: str | None = None
    year: str | None = None
    container_title: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publisher: str | None = None
    doi: str | None = None
    pmid: str | None = None
    isbn: str | None = None
    url: str | None = None
    item_type: str | None = None


class SourceCandidate(StrictModel):
    """One source-located candidate citation."""

    source_index: int = Field(ge=1)
    source_locator: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)
    structured: StructuredReference | None = None
    section_confirmed: bool = True


class ExtractedDocument(StrictModel):
    """Locally extracted document content."""

    input_path: str
    file_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidates: list[SourceCandidate]


class Creator(StrictModel):
    """A Zotero-compatible creator."""

    creator_type: str = "author"
    first_name: str | None = None
    last_name: str | None = None
    name: str | None = None

    def comparison_key(self) -> str:
        """Return the creator key used for duplicate comparison."""
        return (self.last_name or self.name or "").casefold().strip()


class ParsedReference(StrictModel):
    """Normalized bibliographic fields."""

    item_type: str
    title: str
    creators: list[Creator] = Field(default_factory=list)
    date: str | None = None
    container_title: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publisher: str | None = None
    place: str | None = None
    doi: str | None = None
    pmid: str | None = None
    isbn: str | None = None
    issn: str | None = None
    url: str | None = None
    language: str | None = None
    abstract: str | None = None
    tags: list[str] = Field(default_factory=list)

    def year(self) -> str | None:
        """Return the first four-digit comparison year."""
        if self.date is None:
            return None
        for token in self.date.split():
            if len(token) == _YEAR_LENGTH and token.isdigit():
                return token
        return None

    def first_creator_key(self) -> str:
        """Return the first creator comparison key."""
        return self.creators[0].comparison_key() if self.creators else ""


class Quality(StrictModel):
    """Parsing confidence and warnings."""

    parse_status: ParseStatus
    confidence: float = Field(ge=0.0, le=1.0)
    warnings: list[str] = Field(default_factory=list)


class DuplicateInfo(StrictModel):
    """Duplicate match details."""

    status: str = "none"
    matched_item_key: str | None = None
    reason: str | None = None


class ReferenceRecord(StrictModel):
    """Complete traceable record used by the plan."""

    schema_version: str = "reference-record-v1"
    source: SourceCandidate
    parsed: ParsedReference
    quality: Quality
    duplicate: DuplicateInfo = Field(default_factory=DuplicateInfo)
    decision: Decision


class ExistingItem(StrictModel):
    """Minimal existing Zotero item used for duplicate matching."""

    key: str
    parsed: ParsedReference


class TargetLibrary(StrictModel):
    """Approved personal-library destination."""

    user_id: int = Field(ge=0)
    collection_key: str | None = None
    collection_name: str | None = None
    create_collection: bool = False

    @model_validator(mode="after")
    def validate_collection_intent(self) -> Self:
        """Reject contradictory existing and create-if-missing destinations."""
        if self.create_collection and (self.collection_key is not None or not self.collection_name):
            raise PydanticCustomError(
                _COLLECTION_INTENT_ERROR,
                _COLLECTION_INTENT_MESSAGE,
            )
        return self


class Manifest(StrictModel):
    """Immutable import plan."""

    schema_version: str = "manifest-v1"
    parser_version: str = "0.2.1"
    input_path: str
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    target: TargetLibrary
    records: list[ReferenceRecord]

    @classmethod
    def build(
        cls,
        *,
        input_path: Path,
        input_sha256: str,
        target: TargetLibrary,
        records: list[ReferenceRecord],
    ) -> Self:
        """Build a manifest from one immutable preview plan."""
        return cls(
            input_path=str(input_path),
            input_sha256=input_sha256,
            target=target,
            records=records,
        )

    def content_sha256(self) -> str:
        """Hash the canonical machine-consumed plan."""
        payload = self.model_dump(mode="json", exclude_none=True)
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    def approval_binding(self) -> str:
        """Bind source, manifest, user, and collection."""
        collection = self.target.collection_key or (
            f"CREATE:{self.target.collection_name}" if self.target.create_collection else "ROOT"
        )
        raw = (
            f"approval-v1\0{self.input_sha256}\0{self.content_sha256()}"
            f"\0user:{self.target.user_id}\0{collection}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()


class Approval(StrictModel):
    """Approval bound to one exact manifest and destination."""

    schema_version: str = "approval-v1"
    binding_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class CreateSuccess(StrictModel):
    """One item-level Zotero create success."""

    index: int = Field(ge=0)
    key: str
    version: int = Field(ge=0)


class CreateFailure(StrictModel):
    """One item-level Zotero create failure."""

    index: int = Field(ge=0)
    code: int
    message: str


class CreateBatchResponse(StrictModel):
    """Normalized per-item create response."""

    successes: list[CreateSuccess]
    failures: list[CreateFailure]


class ItemOutcome(StrictModel):
    """Final receipt line."""

    source_index: int
    status: OutcomeStatus
    zotero_key: str | None = None
    detail: str | None = None


class Receipt(StrictModel):
    """Machine-readable import result."""

    schema_version: str = "receipt-v1"
    manifest_sha256: str
    outcomes: list[ItemOutcome]
