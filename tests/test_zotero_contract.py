from kaic_zotero_push.models import CreateBatchResponse, JsonValue
from kaic_zotero_push.zotero.responses import normalize_create_response, partition_batches


def test_normalize_create_response_when_api_uses_successful() -> None:
    # Given
    payload: dict[str, JsonValue] = {
        "successful": {"0": {"key": "AAAA1111", "version": 7}},
        "failed": {"1": {"code": 400, "message": "bad field"}},
        "unchanged": {},
    }

    # When
    response = normalize_create_response(payload, expected_count=2)

    # Then
    assert isinstance(response, CreateBatchResponse)
    assert response.successes[0].key == "AAAA1111"
    assert response.failures[0].index == 1


def test_normalize_create_response_when_api_uses_string_success() -> None:
    # Given
    payload: dict[str, JsonValue] = {
        "success": {"0": "ITEMKEY"},
        "successful": {},
        "failed": {},
    }

    # When
    response = normalize_create_response(payload, expected_count=1)

    # Then
    assert response.successes[0].key == "ITEMKEY"
    assert response.successes[0].version == 0
    assert response.failures == []


def test_normalize_create_response_when_both_success_maps_overlap_prefers_object() -> None:
    # Given
    payload: dict[str, JsonValue] = {
        "success": {"0": "ITEMKEY"},
        "successful": {"0": {"key": "ITEMKEY", "version": 9}},
        "failed": {},
    }

    # When
    response = normalize_create_response(payload, expected_count=1)

    # Then
    assert len(response.successes) == 1
    assert response.successes[0].version == 9


def test_normalize_create_response_when_success_is_known_preserves_key_for_reconciliation() -> None:
    # Given
    payload: dict[str, JsonValue] = {
        "success": {"0": "ITEMKEY"},
        "failed": {},
    }

    # When
    response = normalize_create_response(payload, expected_count=2)

    # Then
    assert response.successes[0].key == "ITEMKEY"
    assert response.failures[0].index == 1


def test_normalize_create_response_when_failure_shape_is_malformed_keeps_success() -> None:
    # Given
    payload: dict[str, JsonValue] = {
        "success": {"0": "ITEMKEY"},
        "failed": {"1": "unexpected"},
    }

    # When
    response = normalize_create_response(payload, expected_count=2)

    # Then
    assert response.successes[0].key == "ITEMKEY"
    assert response.failures[0].index == 1


def test_partition_batches_when_more_than_fifty_items() -> None:
    # Given
    items = list(range(101))

    # When
    batches = partition_batches(items)

    # Then
    assert [len(batch) for batch in batches] == [50, 50, 1]
