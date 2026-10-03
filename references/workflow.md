# Document-reference import workflow

Use only the section relevant to the current request. Run commands from the skill's project
directory; initial setup and credential recovery belong in
[security-policy.md](security-policy.md). Parsing and duplicate criteria belong in
[citation-mapping.md](citation-mapping.md).

## 1. Select preview mode and destination

For local extraction/parsing only, without credentials or remote duplicate lookup:

~~~powershell
uv run kaic-zotero-push preview "D:\path\references.txt" --offline
~~~

Do not interpret "check only" as a request to register or always as offline: checking duplicates
against Zotero requires an online no-write preview. Offline accepts no destination and cannot
proceed to approval or commit. If an offline check later becomes a registration request, make
a new online preview and obtain approval of that plan.

For an online preview, use exactly one destination option:

~~~powershell
uv run kaic-zotero-push preview "D:\path\references.docx" --collection "작업치료 연구"
uv run kaic-zotero-push preview "D:\path\references.docx" --collection-key "ABCD1234"
uv run kaic-zotero-push preview "D:\path\references.docx" --library-root
~~~

- A collection name must resolve exactly and uniquely. For multiple matches, show candidate names,
  parent paths, and keys and ask the user to choose; never select the first or create another.
- A collection key selects that exact existing collection.
- Library root requires explicit opt-in; destination omission is not root.
- A missing exact collection name appears as `새 컬렉션 생성 예정`. Preview creates no collection;
  approval must include its exact root-collection creation intent.
- For a registration request with no destination, derive a collection candidate from the input
  filename stem, tell the user it is a proposal, then create the no-write preview:

~~~powershell
uv run kaic-zotero-push preview "D:\path\sample.docx" --collection "sample" --proposed-collection
~~~

The proposal is not approval. A different destination requires a new preview rather than editing
the existing manifest.

## 2. Present the complete preview

Read the generated `preview.md` and report:

- input file and discovered reference count;
- planned creations, exact duplicates, review-needed records, and parse failures;
- exact existing collection name/key, explicit root, or proposed/new collection name;
- whether the collection exists or will be created after approval;
- every reference in all four categories, preserving its source number, parsed fields, and
  applicable reason/warning code, including missing metadata;
- the run directory needed for the next turn.

Explain that Zotero has not changed and that parsing eligibility is not external bibliography
verification. Preserve the complete list; counts alone are not the approval information.
For "preview", "dry run", "check only", or equivalent requests, stop without asking for approval.
For registration, show the plan and wait for concrete user approval.

## 3. Approve the displayed plan and import

Read [security-policy.md](security-policy.md) before any approved write.
Approval binds the input SHA-256, complete manifest SHA-256, personal user ID, and exact existing
collection key, explicit root, or missing-collection creation intent.

Only after the user approves that displayed plan:

~~~powershell
uv run kaic-zotero-push approve ".runs\<run-id>"
uv run kaic-zotero-push commit ".runs\<run-id>"
~~~

One concrete approval covers both commands and read-back; do not ask again between them.
Across turns, retain the same displayed run and approval. Neither a general import request nor
an approval for another run authorizes these commands.
Both commands recheck the current original-file SHA-256. A changed/missing source, manifest,
user, or destination requires a new preview and approval. Never edit the manifest/approval
to bypass checks or overwrite an existing approval.

Commit rechecks ownership and write access, refreshes destination-scoped remote duplicates,
validates against live item templates, and performs read-back of created item keys.
An approved missing root collection is created only at commit; its persisted key is reused for
items, verification, and resume. Existing items are not moved or added to that collection.
If API mechanics fail, read [zotero-api-contract.md](zotero-api-contract.md).

Report the actual resolved destination name and key, including a newly created collection, or
explicit root; include the receipt path and separate counts for these exact states:

| State | Report as |
|---|---|
| `created_verified` | Confirmed creation and placement; the only success count |
| `created_unverified` | Creation response known, read-back incomplete |
| `duplicate_skipped` | Confirmed duplicate excluded |
| `needs_review` | Uncertain parsing or duplicate classification |
| `parse_failed` | Extraction candidate could not be parsed |
| `write_failed` | Write failed or an unresolved outcome requiring inspection |
| `not_attempted` | No attempt after a blocking failure |

Read-back checks item type, title, supplied DOI, and destination placement. It does not verify
authors, year, every field, DOI existence, or publisher bibliography. Do not report unknown
submissions or `created_unverified` as success.

## 4. Resume the same run safely

Use the previous partial run, not a new import:

~~~powershell
uv run kaic-zotero-push resume ".runs\<run-id>"
~~~

Confirm which run the user intends if it is unclear. Preserve the approved input and destination;
the same approval checks still apply. Read [security-policy.md](security-policy.md) before
resuming writes.

- Preserve `created_verified` outcomes and never create those items again.
- Recheck known unverified keys before considering further writes.
- Refresh destination-scoped duplicates and retry only eligible failures.
- If a response was lost, reconcile the same run's stored token and remote state. Do not blindly
  resend, generate a replacement token, or start a new run to retry an unknown submission.
- Persist and reuse a created collection key; never create the collection twice.
- Completed receipts are returned without rewriting history.
- Unfinished legacy batches without source mappings require reconciliation before writing;
  report that concrete limitation rather than bypassing it.
- Never delete successful items to simulate rollback.

Consult [zotero-api-contract.md](zotero-api-contract.md) for API-specific recovery; it is not
required for an ordinary successful preview.
