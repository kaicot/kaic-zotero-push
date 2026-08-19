import httpx2

from kaic_zotero_push.zotero.client import ZoteroClient
from kaic_zotero_push.zotero.models import ZoteroItemPayload


def test_current_key_when_credentials_are_valid() -> None:
    # Given
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.headers["Zotero-API-Key"] == "test-secret"
        assert request.headers["Zotero-API-Version"] == "3"
        assert "key=" not in str(request.url)
        return httpx2.Response(
            200,
            json={
                "userID": 123,
                "username": "tester",
                "access": {"user": {"library": True, "files": False}},
            },
        )

    transport = httpx2.MockTransport(handler)

    # When
    with ZoteroClient(
        api_key="test-secret",
        base_url="https://api.zotero.test",
        transport=transport,
    ) as client:
        access = client.current_key()

    # Then
    assert access.user_id == 123
    assert access.can_write is True


def test_create_items_when_write_token_is_provided() -> None:
    # Given
    def handler(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "POST"
        assert request.headers["Zotero-Write-Token"] == "a" * 32
        return httpx2.Response(
            200,
            json={"successful": {"0": {"key": "ITEM1", "version": 1}}},
        )

    transport = httpx2.MockTransport(handler)

    # When
    with ZoteroClient(
        api_key="test-secret",
        base_url="https://api.zotero.test",
        transport=transport,
    ) as client:
        response = client.create_items(
            user_id=123,
            items=[ZoteroItemPayload(root={"itemType": "journalArticle", "title": "Title"})],
            write_token="a" * 32,
        )

    # Then
    assert response.root["successful"] == {"0": {"key": "ITEM1", "version": 1}}
