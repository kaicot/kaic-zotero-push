# Security policy

## Credentials

- Store the Zotero API key only through `kaic-zotero-push configure`.
- The runtime store is Windows Credential Manager via `keyring`.
- Never place the key in `.env`, JSON, Markdown, source code, shell history, URLs, logs, run
  artifacts, or chat messages.
- Send the key only as the `Zotero-API-Key` request header.
- Use a dedicated key limited to personal-library read/write access. File and group permissions
  are unnecessary for v0.1.

## Documents and metadata

- Parse the input document locally.
- Never copy the original document into `.runs`.
- Never upload the document, article PDFs, or attachments to Zotero.
- Run artifacts can contain citation text. Keep `.runs/` private and out of Git.
- v0.1 performs no title-search enrichment and sends no source document to an external metadata
  service.

## Approval boundary

The approval hash binds the exact input bytes, manifest, personal user ID, and collection key.
Any change invalidates approval. Do not manually edit run artifacts to bypass this check.

## Incident handling

If a key may have appeared in output or Git history:

1. Revoke it immediately in Zotero account settings.
2. Create a new least-privilege key.
3. Run `kaic-zotero-push configure` again.
4. Remove leaked material from all shared systems; changing the latest Git file alone is not
   sufficient if the key entered history.
