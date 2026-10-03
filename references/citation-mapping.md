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

## DOCX reference-section boundaries

- Begin only at a standalone `References`, `Bibliography`, or `참고문헌` heading.
- Stop immediately at normal-style headings or text markers for `Table S1/S2`, numbered tables,
  `Supplementary`, `Supplementary Table`, `Supporting Information`, `Appendix`, `Acknowledgments`,
  or `Figure`.
- Exclude the terminator and every later caption, footnote, paragraph, and table. Preserve
  unnumbered references up to that boundary; do not infer the boundary from numbering.
- If no explicit end boundary is found, keep located candidates but mark the section unconfirmed
  so its references remain `needs_review`, not automatically eligible through the document end.

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
authors remain personal creators. Title, date, publisher, place, and source-provided URL or DOI are
mapped only when present in the source.

Use report markers as evidence only when author, title, publisher, and year can be separated
from the source. Preserve supplied journal abbreviations, initials, volume, issue, page ranges,
and article numbers; do not expand or enrich them through external search. A source-provided
URL or DOI is not a claim that it was externally validated.

If review finds an incorrect field despite no automatic warnings, explain it and do not commit
that plan. Prepare a corrected source-derived input and new preview; never patch an approved
manifest or claim parsing verified the bibliography.

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

Remote duplicate matching is scoped to the explicit requested destination. An existing item in
another collection does not block creation for the current collection. The personal-library root
is in scope only when the user explicitly selects `--library-root`; an omitted destination is not
a root fallback. A newly requested collection has no remote items in scope during preview.
Repeated references in the same input are always `needs_review`, even when a matching remote item
also exists. Show both compared source numbers and the reason; if source citation numbers are not
available, label them as extraction-order numbers.

1. Exact normalized DOI.
2. Exact PMID or ISBN.
3. Exact normalized title + year + first creator.
4. High title similarity with corroborating year or creator.
5. Title-only similarity or conflicting core fields becomes `needs_review`.

Exact duplicates are skipped. Possible duplicates are never automatically created.

During commit rechecking, preserve confirmed matches as `duplicate_skipped` and uncertain matches
as `needs_review`; do not recast review-needed records as confirmed duplicates.
