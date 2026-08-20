"""Zotero batch response normalization."""

from collections.abc import Mapping, Sequence
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

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
    version: int = 0


class _ApiFailure(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    code: int = 500
    message: str = "Zotero item creation failed."


class _ApiSuccessMaps(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")

    success: dict[int, str | _ApiSuccess] = Field(default_factory=dict)
    successful: dict[int, _ApiSuccess] = Field(default_factory=dict)


class _ApiCreateEnvelope(_ApiSuccessMaps):
    unchanged: dict[int, JsonValue] = Field(default_factory=dict)
    failed: dict[int, _ApiFailure] = Field(default_factory=dict)


def extract_create_successes(payload: Mapping[str, JsonValue]) -> list[CreateSuccess]:
    """Extract every recognizable success key before full response normalization."""
    try:
        envelope = _ApiSuccessMaps.model_validate(payload)
    except ValidationError as error:
        raise ZoteroApiError(
            status_code=200,
            detail="Malformed item-level success response.",
        ) from error
    success_map: dict[int, CreateSuccess] = {}
    for index, value in envelope.success.items():
        if isinstance(value, str):
            success_map[index] = CreateSuccess(index=index, key=value, version=0)
        else:
            success_map[index] = CreateSuccess(
                index=index,
                key=value.key,
                version=value.version,
            )
    success_map.update(
        {
            index: CreateSuccess(index=index, key=value.key, version=value.version)
            for index, value in envelope.successful.items()
        }
    )
    return [value for _, value in sorted(success_map.items())]


def normalize_create_response(
    payload: Mapping[str, JsonValue],
    *,
    expected_count: int,
) -> CreateBatchResponse:
    """Normalize both documented Zotero success-map spellings."""
    successes = extract_create_successes(payload)
    success_indices = {success.index for success in successes}
    try:
        envelope = _ApiCreateEnvelope.model_validate(payload)
    except ValidationError as error:
        if successes:
            return CreateBatchResponse(
                successes=successes,
                failures=[
                    CreateFailure(
                        index=index,
                        code=500,
                        message="Malformed item-level failure response; safe retry required.",
                    )
                    for index in sorted(set(range(expected_count)) - success_indices)
                ],
            )
        raise ZoteroApiError(
            status_code=200,
            detail="Malformed item-level response.",
        ) from error
    failures = [
        CreateFailure(index=index, code=value.code, message=value.message)
        for index, value in sorted(envelope.failed.items())
        if index not in success_indices
    ]
    failures.extend(
        CreateFailure(index=index, code=412, message="Unexpected unchanged create result.")
        for index in sorted(envelope.unchanged)
    )
    disposition_indices = success_indices | {item.index for item in failures}
    expected_indices = set(range(expected_count))
    missing_indices = expected_indices - disposition_indices
    if missing_indices and successes:
        failures.extend(
            CreateFailure(
                index=index,
                code=500,
                message="Missing item-level disposition; retry with the persisted write token.",
            )
            for index in sorted(missing_indices)
        )
    elif disposition_indices != expected_indices:
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
