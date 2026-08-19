"""Typed Zotero API boundary models."""

from __future__ import annotations

from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

from kaic_zotero_push.models import JsonValue


class ApiModel(BaseModel):
    """Zotero response model that tolerates additive API fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="ignore")


class UserLibraryAccess(ApiModel):
    """Personal-library access flags."""

    library: bool = False
    files: bool = False


class AccessMap(ApiModel):
    """Key access map."""

    user: UserLibraryAccess


class CurrentKeyResponse(ApiModel):
    """Raw `/keys/current` response."""

    user_id: int = Field(alias="userID")
    username: str
    access: AccessMap


class KeyAccess(ApiModel):
    """Application-facing key identity and permission."""

    user_id: int
    username: str
    can_write: bool


class CollectionData(ApiModel):
    """Raw collection data."""

    key: str
    name: str
    parent_collection: str | Literal[False] = Field(alias="parentCollection", default=False)


class CollectionEnvelope(ApiModel):
    """Raw collection envelope."""

    key: str
    data: CollectionData


class Collection(ApiModel):
    """Application-facing collection identity."""

    key: str
    name: str
    parent_key: str | None = None


class ApiCreator(ApiModel):
    """Raw Zotero creator."""

    creator_type: str = Field(alias="creatorType", default="author")
    first_name: str | None = Field(alias="firstName", default=None)
    last_name: str | None = Field(alias="lastName", default=None)
    name: str | None = None


class ApiItemData(ApiModel):
    """Raw Zotero item fields needed by this application."""

    item_type: str = Field(alias="itemType")
    title: str = ""
    creators: list[ApiCreator] = Field(default_factory=list)
    date: str | None = None
    publication_title: str | None = Field(alias="publicationTitle", default=None)
    book_title: str | None = Field(alias="bookTitle", default=None)
    doi: str | None = Field(alias="DOI", default=None)
    isbn: str | None = Field(alias="ISBN", default=None)
    url: str | None = None
    extra: str | None = None
    collections: list[str] = Field(default_factory=list)


class ApiItemEnvelope(ApiModel):
    """Raw Zotero item envelope."""

    key: str
    data: ApiItemData


class RemoteItem(ApiModel):
    """Application-facing remote item used for verification."""

    key: str
    item_type: str
    title: str
    doi: str | None = None
    date: str | None = None
    first_creator: str = ""
    collections: list[str] = Field(default_factory=list)


class ZoteroItemPayload(RootModel[dict[str, JsonValue]]):
    """Editable metadata-only Zotero item JSON."""


class ZoteroResponsePayload(RootModel[dict[str, JsonValue]]):
    """Generic Zotero object response used by create normalization."""
