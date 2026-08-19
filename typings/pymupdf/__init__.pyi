from collections.abc import Iterator
from types import TracebackType
from typing import Literal, Self

type TextBlock = tuple[float, float, float, float, str, int, int, int]

class Page:
    def get_text(self, option: Literal["blocks"]) -> list[TextBlock]: ...

class Document:
    needs_pass: bool
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    def __iter__(self) -> Iterator[Page]: ...

def open(filename: str) -> Document: ...
