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
`.hwp`, `.hwpx`, and OCR are outside v0.1.

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
- run directory.

Say explicitly that Zotero has not been changed.

For "preview", "dry run", "check only", or equivalent requests, stop here without asking for
approval.

### 3. Obtain explicit approval

Approval is bound to:

- the input SHA-256;
- the complete manifest SHA-256;
- the Zotero personal user ID;
- the collection key or library root.

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
item keys for verification.

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
- Do not silently create a missing collection in v0.1.
- Bind approval and writes to the collection key, never only the display name.

## Scope limits

Decline requests to update, merge, or delete existing Zotero items; upload files; use group
libraries; OCR scans; or process HWP/HWPX. Explain that these are outside v0.1 and do not attempt
an improvised workaround.
