---
name: kaic-zotero-push
description: Extract and preview references from DOCX, XLSX, CSV, Markdown, text, or text-based PDF documents, then import new metadata-only items into a Zotero personal library after explicit approval. Use for document-reference registration, no-write previews, or resuming a previous import.
---

# kaic-zotero-push

Import a document's references into the user's Zotero **personal library**. Follow the user's
explicit instructions and existing authorization; keep the exact document, destination, and run
in scope across turns.

## Essential rules

1. Preview before every write. "Add", "import", or "do it now" is not approval of an unseen plan.
2. Show the full preview and stop for explicit approval before `approve` or `commit`. One
   concrete approval covers that unchanged plan's approval record, import, and read-back.
3. This CLI creates new metadata-only items; it does not update, merge, delete, or upload files.
4. Never write to group libraries or invent missing metadata. Hold uncertain parsing and possible
   duplicates as `needs_review`.
5. Never expose an API key in prompts, command arguments, URLs, files, logs, receipts, or responses.
6. Success means `created_verified` after read-back, not merely a creation response. This checks
   creation and destination placement, not publisher bibliography or DOI existence.
7. A changed/missing source, changed manifest, user, or destination requires a new preview and
   approval. Never patch `manifest.json` or `approval.json` or overwrite an existing approval.
8. Resume the same run; preserve verified outcomes. An unknown submission needs reconciliation,
   not a blind new import, new token, or deletion of successful items to simulate rollback.

## Choose the task

- **Check only / preview / dry run:** create and present a no-write preview, then stop without
  asking for registration approval. Use `--offline` for local extraction/parsing only; an online
  preview is needed to check remote duplicates and requires a destination.
- **Register references:** create and present the preview, wait for explicit approval, then
  approve, commit, and report read-back results without requesting approval again between steps.
- **Continue an approved plan:** use the displayed run and existing concrete approval; do not
  restart with a new preview unless the bound plan changed.
- **Resume failures:** identify the previous run and resume it rather than creating a new import.
  If its identity is unclear, ask which run; do not guess or select an unrelated recent run.

Read the relevant section of [references/workflow.md](references/workflow.md) for commands,
destination selection, full preview reporting, or safe resume. Do not load every reference by
default.

## Inputs and preparation

Support `.docx`, `.xlsx`, `.csv`, `.md`, `.txt`, and text-based `.pdf`.
Reject encrypted, damaged, unsupported, or non-text-extractable inputs. Scanned PDFs, images,
HWP/HWPX, and OCR are unsupported.

Run the CLI from this skill's project directory. Use an existing working installation and
credential configuration; do not run `configure` on every request.
Read [references/security-policy.md](references/security-policy.md) before initial setup,
credential/permission recovery, or any approved write. It contains the setup commands.

## Preview and review

An online preview needs exactly one destination: a collection name, existing collection key,
or explicit library root. A missing destination never implies root. For a destination-free
registration request, propose the input filename stem as a collection and label it as a proposal.
An ambiguous name requires the user's choice; a missing exact name is only a proposed creation
until the preview is approved. Offline previews accept no destination and cannot be approved.

Read the generated `preview.md`; present its counts, exact destination and existing/new state,
all references with source numbers, fields, reasons/warnings, and the run directory.
State that Zotero is unchanged and the preview is a parsing plan, not verified bibliography.
Do not omit review-needed or failed references from the approval information.

Remote duplicates are scoped to the requested destination, not the whole library. A match only
in another collection does not block creation. Repeats within the input remain `needs_review`,
even if a remote match also exists.

Read [references/citation-mapping.md](references/citation-mapping.md) when processing DOCX
reference-section boundaries, checking parsed fields, or resolving item types/duplicates.
If a parsed field is wrong despite no warnings, stop: explain the mismatch and prepare a
corrected source-derived input and new preview instead of editing an approved manifest.
Never expand abbreviations or fill missing metadata through external search.

## Approved import and recovery

After approval, follow the approval/import section of
[references/workflow.md](references/workflow.md). Report the resolved destination name and key
(or explicit root), receipt path, and exact outcome counts. Count only `created_verified`
as success; retain `created_unverified`, `duplicate_skipped`, `needs_review`, `parse_failed`,
`write_failed`, and `not_attempted` separately.

For partial or uncertain outcomes, read the resume section of that workflow. Keep completed
receipts immutable and reconcile unfinished legacy records without source mappings before writes.
Read [references/zotero-api-contract.md](references/zotero-api-contract.md) only when diagnosing
API failures or inspecting batch, collection-creation, and read-back mechanics.

## Scope limits

No existing-item modification, merge, deletion, file upload, group-library writing, OCR, HWP/HWPX,
or external metadata enrichment is provided by this CLI.
If the user explicitly requests cleanup, preserve it as a separate scoped task that identifies
targets, for example from receipt item keys. State the tool limitation; do not silently omit the
request or promise this CLI will perform it.
