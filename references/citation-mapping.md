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

## Duplicate order

1. Exact normalized DOI.
2. Exact PMID or ISBN.
3. Exact normalized title + year + first creator.
4. High title similarity with corroborating year or creator.
5. Title-only similarity or conflicting core fields becomes `needs_review`.

Exact duplicates are skipped. Possible duplicates are never automatically created.
