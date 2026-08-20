---
name: kaic-zotero-push
description: Extract references from local or uploaded DOCX, XLSX, CSV, Markdown, text, and text-based PDF files; preview normalized and deduplicated bibliographic records; and create new metadata-only items in the user's Zotero personal library only after explicit approval. Use when the user asks to import, register, save, or add a document's references or paper list to Zotero.
---

# kaic-zotero-push

Safely import bibliographic references into a user's Zotero **personal library**.

## Non-negotiable rules

1. Preview before every write. A request to "add", "import", or "do it now" does not bypass the preview.
2. After showing the preview, stop and obtain explicit user approval before running `approve` or `commit`.
3. Create new metadata-only items only. Never update, merge, or delete existing items.
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
`.hwp`, `.hwpx`, and OCR are outside v0.2.

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
uv run kaic-zotero-push preview "D:\path\references.docx"
uv run kaic-zotero-push preview "D:\path\references.docx" --collection "작업치료 연구"
```

For local parsing without credentials or remote duplicate lookup:

```powershell
uv run kaic-zotero-push preview "D:\path\references.txt" --offline
```

Use `--offline` only for check-only requests. An offline run cannot be approved for writing
because it is not bound to a verified Zotero user or remote duplicate state.

### 2. Present the preview

Read the generated `preview.md` and report:

- input file;
- discovered count;
- planned creations;
- exact duplicates;
- review-needed records;
- parse failures;
- personal-library collection or root;
- representative planned items;
- missing metadata warning codes;
- whether the exact named collection will be created after approval;
- run directory.

Say explicitly that Zotero has not been changed.

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

If the input, manifest, user, or collection changes, show a new preview and request approval
again. Never edit `manifest.json` or `approval.json`.

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

Report receipt states exactly:

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

Resume preserves verified outcomes, rechecks known unverified keys, refreshes remote duplicates,
and retries only eligible failures. Never delete successful items to simulate rollback.

## Collection handling

- Resolve an exact unique collection name.
- If a name is ambiguous, report the candidate keys and ask the user to choose.
- If no collection is given, use the personal-library root.
- If the exact name is missing, show `새 컬렉션 생성 예정` in the preview.
- Create a missing root collection only after the user approves that exact preview.
- Persist and reuse the created collection key during resume; never create it twice.
- Bind approval to the existing key or exact create-if-missing name, never an unapproved
  destination.

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

## Scope limits

Decline requests to update, merge, or delete existing Zotero items; upload files; use group
libraries; OCR scans; or process HWP/HWPX. Explain that these are outside v0.2.1 and do not attempt
an improvised workaround.
