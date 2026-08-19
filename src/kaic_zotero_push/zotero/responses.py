"""Zotero batch response normalization."""

from collections.abc import Mapping, Sequence
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field

from kaic_zotero_push.errors import ZoteroApiError
from kaic_zotero_push.models import (
    CreateBatchResponse,
    CreateFailure,
    CreateSuccess,
    JsonValue,
)

_MAX_BATCH_SIZE: Final = 50


class _ApiSuccess(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    key: str
    version: int


class _ApiFailure(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    code: int = 500
    message: str = "Zotero item creation failed."


class _ApiCreateEnvelope(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    success: dict[int, _ApiSuccess] = Field(default_factory=dict)
    successful: dict[int, _ApiSuccess] = Field(default_factory=dict)
    unchanged: dict[int, JsonValue] = Field(default_factory=dict)
    failed: dict[int, _ApiFailure] = Field(default_factory=dict)


def normalize_create_response(
    payload: Mapping[str, JsonValue],
    *,
    expected_count: int,
) -> CreateBatchResponse:
    """Normalize both documented Zotero success-map spellings."""
    envelope = _ApiCreateEnvelope.model_validate(payload)
    success_map = envelope.success | envelope.successful
    successes = [
        CreateSuccess(index=index, key=value.key, version=value.version)
        for index, value in sorted(success_map.items())
    ]
    failures = [
        CreateFailure(index=index, code=value.code, message=value.message)
        for index, value in sorted(envelope.failed.items())
    ]
    failures.extend(
        CreateFailure(index=index, code=412, message="Unexpected unchanged create result.")
        for index in sorted(envelope.unchanged)
    )
    disposition_indices = {item.index for item in successes} | {item.index for item in failures}
    if disposition_indices != set(range(expected_count)):
        raise ZoteroApiError(
            status_code=200,
            detail="Malformed item-level response: missing or duplicate indices.",
        )
    return CreateBatchResponse(successes=successes, failures=failures)


def partition_batches[T](
    items: Sequence[T],
    *,
    size: int = _MAX_BATCH_SIZE,
) -> list[list[T]]:
    """Partition items without exceeding Zotero's 50-object limit."""
    if size < 1 or size > _MAX_BATCH_SIZE:
        raise ZoteroApiError(status_code=413, detail="Batch size must be between 1 and 50.")
    return [list(items[start : start + size]) for start in range(0, len(items), size)]
