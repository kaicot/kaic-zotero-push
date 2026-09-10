# Security policy

## Credentials

- Store the Zotero API key only through `kaic-zotero-push configure`.
- The runtime store is Windows Credential Manager via `keyring`.
- Never place the key in `.env`, JSON, Markdown, source code, shell history, URLs, logs, run
  artifacts, or chat messages.
- Send the key only as the `Zotero-API-Key` request header.
- Use a dedicated key limited to personal-library read/write access. File and group permissions
  are unnecessary for v0.2.

## Documents and metadata

- Parse the input document locally.
- Never copy the original document into `.runs`.
- Never upload the document, article PDFs, or attachments to Zotero.
- Run artifacts can contain citation text. Keep `.runs/` private and out of Git.
- v0.2 performs no title-search enrichment and sends no source document to an external metadata
  service.

## Approval boundary

The approval hash binds the exact input bytes, manifest, personal user ID, and destination:
an existing collection key, explicit library root, or exact missing-collection creation intent.
`approve` and `commit` each recompute the original input SHA-256 and compare it with the
manifest's `input_sha256`. A missing or changed original file, manifest, user, or destination
invalidates approval and requires a new preview and concrete user approval. A missing collection
is created only after approval, and its resolved key is kept in a separate durable state file.
Do not manually edit run artifacts to bypass these checks.

One concrete user approval covers the displayed plan's `approve`, `commit`, and read-back
verification. It does not authorize a changed plan. Offline previews have no verified user or
remote duplicate state and cannot be approved or committed.

If a write response is lost or otherwise leaves creation uncertain, retain and reconcile the same
run's durable token and state. Do not create a new run for a blind re-import.

## Incident handling

If a key may have appeared in output or Git history:

1. Revoke it immediately in Zotero account settings.
2. Create a new least-privilege key.
3. Run `kaic-zotero-push configure` again.
4. Remove leaked material from all shared systems; changing the latest Git file alone is not
   sufficient if the key entered history.
