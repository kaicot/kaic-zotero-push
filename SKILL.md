---
name: kaic-zotero-push
description: Extract references from local or uploaded DOCX, XLSX, CSV, Markdown, text, and text-based PDF files; preview normalized and deduplicated bibliographic records; and create new metadata-only items in the user's Zotero personal library only after explicit approval. Use when the user asks to import, register, save, or add a document's references or paper list to Zotero.
---

# kaic-zotero-push

Safely import bibliographic references into a user's Zotero **personal library**.

Follow the user's explicit instructions and existing authorization; skill guidance does not
override them. Keep the exact approved document and destination in scope across turns.

## Non-negotiable rules

1. Preview before every write. A request to "add", "import", or "do it now" does not bypass the preview.
2. After showing the preview, stop and obtain explicit user approval before running `approve` or `commit`.
3. This CLI creates new metadata-only items only; it has no update, merge, or delete feature.
4. Never upload source documents, PDFs, or attachments.
5. Never write to group libraries.
6. Never invent missing metadata. Quarantine low-confidence records and possible duplicates.
7. Never expose an API key in a prompt, command argument, URL, file, log, receipt, or response.
8. Report success only after the created item has been fetched again and verified.

Read [references/security-policy.md](references/security-policy.md) before setup or writes.
Read [references/zotero-api-contract.md](references/zotero-api-contract.md) before diagnosing API
failures. Read [references/citation-mapping.md](references/citation-mapping.md) when reviewing
parsing or item-type decisions.

## Supported inputs

Accept:

- `.docx`
- `.xlsx`, `.csv`
- `.md`, `.txt`
- text-based `.pdf`

Reject encrypted, damaged, unsupported, or non-text-extractable inputs. Scanned PDFs, images,
`.hwp`, `.hwpx`, and OCR are outside v0.2.4.

## Setup

From this skill directory:

```powershell
uv sync
uv run kaic-zotero-push configure
```

The configuration command prompts privately, verifies `/keys/current`, and stores the key in
Windows Credential Manager. Recommend a dedicated Zotero key with personal-library
read/write access and no file or group permissions.

## Required workflow

### 1. Create a preview

For a normal Zotero-connected preview:

```powershell
uv run kaic-zotero-push preview "D:\path\references.docx" --collection "작업치료 연구"
uv run kaic-zotero-push preview "D:\path\references.docx" --collection-key "ABCD1234"
uv run kaic-zotero-push preview "D:\path\references.docx" --library-root
```

For local parsing without credentials or remote duplicate lookup:

```powershell
uv run kaic-zotero-push preview "D:\path\references.txt" --offline
```

Use `--offline` only for check-only requests. An offline run cannot be approved for writing
because it is not bound to a verified Zotero user or remote duplicate state.

For an online preview, require exactly one destination: `--collection NAME`,
`--collection-key KEY`, or `--library-root`. Do not run an online preview without one, and do
not combine destination options. `--offline` accepts no destination option and cannot proceed
to `approve` or `commit`.

For a natural-language registration request without a destination, derive a proposed collection
name from the input filename stem, tell the user it is a proposal, and create the no-write
preview with the exact command shape below. The proposal is not an approved destination.

```powershell
uv run kaic-zotero-push preview "D:\path\sample.docx" --collection "sample" --proposed-collection
```

### 2. Present the preview

Read the generated `preview.md` and report:

- input file;
- discovered count;
- planned creations;
- exact duplicates;
- review-needed records;
- parse failures;
- exact destination: existing collection name and key, explicit library root, or proposed/new
  collection name;
- whether the destination is an existing collection or a new collection that will be created;
- every planned, duplicate-skipped, review-needed, and parse-failed reference with its source
  number and applicable reason or warning code;
- missing metadata warning codes;
- run directory.

Say explicitly that Zotero has not been changed and that the preview is a parsing and
destination plan, not verified-bibliography confirmation.

For "preview", "dry run", "check only", or equivalent requests, stop here without asking for
approval.

### 3. Obtain explicit approval

Approval is bound to:

- the input SHA-256;
- the complete manifest SHA-256;
- the Zotero personal user ID;
- the existing collection key, library root, or exact missing-collection creation intent.

After the user approves the displayed preview, and only then:

```powershell
uv run kaic-zotero-push approve ".runs\<run-id>"
```

One concrete approval of the displayed plan authorizes `approve`, `commit`, and read-back; do
not ask again between those steps. `approve` and `commit` each compare the current original-file
SHA-256 with `manifest.json`'s `input_sha256`. If the input is missing or changed, or if the
manifest, user, or destination changed, show a new preview and obtain new approval. Never edit
`manifest.json` or `approval.json`.

### 4. Commit and verify

```powershell
uv run kaic-zotero-push commit ".runs\<run-id>"
```

The command rechecks key ownership and write access, refreshes remote duplicates, validates
payloads against live Zotero item templates, writes no more than 50 items per request, persists
one stable write token per batch, handles item-level partial failures, and fetches successful
item keys for verification. If the preview bound an exact missing collection name, `commit`
creates that root collection only after approval, persists its returned key, and then uses the
same key for every item and read-back check.

Report the resolved collection name and key (including a newly created collection), receipt path,
and these receipt states exactly:

- `created_verified`
- `created_unverified`
- `duplicate_skipped`
- `needs_review`
- `parse_failed`
- `write_failed`
- `not_attempted`

Do not count `created_unverified` as success.

### 5. Resume safely

For a partial run:

```powershell
uv run kaic-zotero-push resume ".runs\<run-id>"
```

Resume the same run directory. It preserves verified outcomes, rechecks known unverified keys,
refreshes remote duplicates, and retries only eligible failures. If a response left creation
unknown, reconcile that run's stored token and remote state; never start a blind new import or
create a new run to retry an unknown outcome. Never delete successful items to simulate rollback.

Completed receipts are returned without rewriting history. Unfinished legacy batch records
without source mappings require reconciliation before writing; report that concrete limitation.

## Collection handling

- Resolve an exact unique collection name.
- If a name is ambiguous, report the candidate keys and ask the user to choose.
- `--library-root` is an intentional opt-in for the personal-library root; never treat an omitted
  destination as root.
- `--collection-key` selects that exact existing collection key. `--collection` resolves an exact
  unique name; do not select the first same-named collection.
- If the exact name is missing, show `새 컬렉션 생성 예정` in the preview.
- Create a missing root collection only after the user approves that exact preview.
- Persist and reuse the created collection key during resume; never create it twice.
- Bind approval to the existing key or exact create-if-missing name, never an unapproved
  destination.
- Scope remote duplicate matching to the requested destination collection; an item found only
  in another collection does not block creation in the current collection.
- Treat repeated references within the same input document as `needs_review`, including when a
  matching remote item also exists.

## Parsing quality gate

- Use structured fields first, then MDPI/Vancouver, then APA, then conservative fallback.
- For DOCX, begin only at a standalone `References`, `Bibliography`, or `참고문헌`
  heading. Stop immediately at normal-style headings or text markers for `Table S1/S2`,
  numbered tables, `Supplementary`, `Supplementary Table`, `Supporting Information`,
  `Appendix`, `Acknowledgments`, or `Figure`.
- Exclude the terminator and every later caption, footnote, paragraph, and table. Preserve
  unnumbered references up to that boundary; do not infer the boundary from numbering.
- If no explicit DOCX end boundary is found, keep the located reference candidates but mark
  their section unconfirmed so they remain `needs_review`.
- A journal article is eligible only when it has a separated title, at least one creator,
  a date or DOI, and a publication title; DOI text must not remain in the title.
- Preserve journal abbreviations, initials, volume, issue, page range or article number exactly
  as provided. Never expand or enrich them through external search.
- Preserve structured and clearly formatted institution-authored reports as `report`.
- Treat `Indicator`, `Press Release`, `User Guide`, `Raw Data`, `Reference Materials`,
  `Valuation Study`, `보고서`, and `지침` as report evidence only when author, title,
  publisher, and year can be separated from the source.
- Preserve report publisher, place, and URL or DOI only when they occur in the input.
- If review reveals an incorrect parsed field despite zero automatic warnings, explain the
  mismatch and do not commit that plan. Prepare a corrected source-derived input and a new
  preview; never patch the approved manifest or claim the parser verified the bibliography.

## Scope limits

The Python CLI has no update, merge, or delete feature; it also does not upload files, write to
group libraries, perform OCR, or process HWP/HWPX. State this as a tool limitation, not a
prohibition on the user. If the user explicitly authorizes cleanup, preserve that request as a
separate, scoped task that first identifies targets (for example, from receipt item keys); do not
silently omit it or claim this CLI will perform it.
