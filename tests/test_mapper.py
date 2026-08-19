from kaic_zotero_push.parsing import parse_candidate
from kaic_zotero_push.zotero.mapper import map_record
from kaic_zotero_push.zotero.models import ZoteroItemPayload


def test_map_record_when_template_contains_supported_fields() -> None:
    # Given
    record = parse_candidate(
        "Smith, J. (2025). Example title. Example Journal. doi:10.1000/example",
        source_index=1,
        source_locator="line=1",
    )
    template = ZoteroItemPayload(
        root={
            "itemType": "journalArticle",
            "title": "",
            "creators": [],
            "date": "",
            "publicationTitle": "",
            "DOI": "",
            "url": "",
            "collections": [],
            "tags": [],
        }
    )

    # When
    payload = map_record(record, template, collection_key="COLL1")

    # Then
    assert payload.root["title"] == "Example title"
    assert payload.root["DOI"] == "10.1000/example"
    assert payload.root["collections"] == ["COLL1"]
    assert "raw_text" not in payload.root
