from types import TracebackType
from typing import Self, final

import pytest
from typer.testing import CliRunner

from kaic_zotero_push import cli
from kaic_zotero_push.zotero.models import KeyAccess


@final
class FakeZoteroClient:
    api_key: str

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def current_key(self) -> KeyAccess:
        return KeyAccess(user_id=123, username="tester", can_write=True)


def test_configure_when_key_omitted_uses_secure_reader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    stored: list[str] = []

    def read_key() -> str:
        return "secret-from-reader"

    def store_key(value: str) -> None:
        stored.append(value)

    monkeypatch.setattr(cli, "read_api_key", read_key)
    monkeypatch.setattr(cli, "ZoteroClient", FakeZoteroClient)
    monkeypatch.setattr(cli, "store_api_key", store_key)

    # When
    result = CliRunner().invoke(cli.app, ["configure"])

    # Then
    assert result.exit_code == 0
    assert stored == ["secret-from-reader"]
