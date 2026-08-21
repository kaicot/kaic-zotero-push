# Citation mapping

## Item types

| Source kind | Zotero `itemType` |
|---|---|
| Journal article | `journalArticle` |
| Preprint | `preprint` |
| Book | `book` |
| Book chapter | `bookSection` |
| Thesis or dissertation | `thesis` |
| Conference paper | `conferencePaper` |
| Report | `report` |
| Web resource | `webpage` |

The parser is conservative. The default is `journalArticle`; explicit structured input or
unambiguous source markers may select another supported type. Ambiguous records must be reviewed,
not guessed.

## Parsing order and journal gate

1. Structured CSV/XLSX fields.
2. MDPI/Vancouver author-title-journal-year-tail citations.
3. APA author-year citations.
4. Conservative fallback.

MDPI/Vancouver parsing removes DOI and URL before splitting fields, preserves semicolon author
order, hyphenated initials, and apostrophes, and stores both page ranges and article numbers in
`pages`. Journal abbreviations remain exactly as supplied. A separated journal and year are
sufficient for online-first articles when volume, issue, and pages are absent.

A `journalArticle` can be created only when its title is separated from the full citation,
`creators` and `container_title` are present, a date or DOI exists, and DOI text is absent from
the title. Failed gates are rendered as stable warning codes and remain `needs_review`.

Report evidence includes `Indicator`, `Press Release`, `User Guide`, `Raw Data`,
`Reference Materials`, `Valuation Study`, `보고서`, and `지침`. Institution-authored reports
preserve the organization in Zotero's single `name` creator field. Clearly supplied personal
authors remain personal creators. Title, date, publisher, place, and verified URL or DOI are
mapped only when present in the source.

## Field mapping

| Internal field | Zotero field |
|---|---|
| `title` | `title` |
| `creators` | `creators` |
| `date` | `date` |
| `container_title` | `publicationTitle` or `bookTitle` |
| `volume`, `issue`, `pages` | same-name fields |
| `publisher`, `place` | same-name fields |
| `doi` | `DOI` |
| `isbn`, `issn` | `ISBN`, `ISSN` |
| `url` | `url` |
| `language` | `language` |
| `abstract` | `abstractNote` |
| `tags` | `tags` |
| `pmid` | `extra` as `PMID: <value>` |

Only fields present in the live `/items/new` template are sent. Creator order is preserved.
Institutional or inseparable names use Zotero's single `name` field.

## Duplicate scope and order

Remote duplicate matching is scoped to the requested destination. An existing item in another
collection does not block creation for the current collection. When no collection is requested,
only root items with an empty collection list are in scope. A newly requested collection has no
remote items in scope during preview. Repeated references in the same input are always
`needs_review`, even when a matching remote item also exists.

1. Exact normalized DOI.
2. Exact PMID or ISBN.
3. Exact normalized title + year + first creator.
4. High title similarity with corroborating year or creator.
5. Title-only similarity or conflicting core fields becomes `needs_review`.

Exact duplicates are skipped. Possible duplicates are never automatically created.
