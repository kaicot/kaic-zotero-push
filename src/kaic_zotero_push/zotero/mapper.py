"""Internal-reference to Zotero-template mapping."""

from kaic_zotero_push.models import Creator, JsonValue, ReferenceRecord
from kaic_zotero_push.zotero.models import ZoteroItemPayload


def _creator_payload(creator: Creator) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {"creatorType": creator.creator_type}
    if creator.name:
        payload["name"] = creator.name
    else:
        payload["firstName"] = creator.first_name or ""
        payload["lastName"] = creator.last_name or ""
    return payload


def map_record(
    record: ReferenceRecord,
    template: ZoteroItemPayload,
    *,
    collection_key: str | None,
) -> ZoteroItemPayload:
    """Fill only fields present in the live Zotero template."""
    payload = dict(template.root)
    parsed = record.parsed
    values: dict[str, JsonValue] = {
        "itemType": parsed.item_type,
        "title": parsed.title,
        "creators": [_creator_payload(creator) for creator in parsed.creators],
        "date": parsed.date,
        "publicationTitle": parsed.container_title,
        "bookTitle": parsed.container_title,
        "volume": parsed.volume,
        "issue": parsed.issue,
        "pages": parsed.pages,
        "publisher": parsed.publisher,
        "place": parsed.place,
        "DOI": parsed.doi,
        "ISBN": parsed.isbn,
        "ISSN": parsed.issn,
        "url": parsed.url,
        "language": parsed.language,
        "abstractNote": parsed.abstract,
        "tags": [{"tag": tag} for tag in parsed.tags],
        "collections": [collection_key] if collection_key else [],
    }
    for key, value in values.items():
        if key in payload and value is not None:
            payload[key] = value
    extras: list[str] = []
    if parsed.pmid:
        extras.append(f"PMID: {parsed.pmid}")
    if extras and "extra" in payload:
        payload["extra"] = "\n".join(extras)
    return ZoteroItemPayload(root=payload)
