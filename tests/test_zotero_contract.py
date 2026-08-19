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


def test_partition_batches_when_more_than_fifty_items() -> None:
    # Given
    items = list(range(101))

    # When
    batches = partition_batches(items)

    # Then
    assert [len(batch) for batch in batches] == [50, 50, 1]
