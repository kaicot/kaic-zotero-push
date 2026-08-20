# Zotero Web API contract

## Required headers

```http
Zotero-API-Key: <credential manager value>
Zotero-API-Version: 3
Content-Type: application/json
User-Agent: kaic-zotero-push/<version>
```

The API key must never be a query parameter.

## Endpoints used

| Purpose | Method and path |
|---|---|
| Key and permission check | `GET /keys/current` |
| Collections | `GET /users/<userID>/collections` |
| Root collection creation | `POST /users/<userID>/collections` |
| Existing top-level items | `GET /users/<userID>/items/top` |
| Live item template | `GET /items/new?itemType=<type>` |
| Batch item creation | `POST /users/<userID>/items` |
| Read-back verification | `GET /users/<userID>/items/<itemKey>` |

## Write invariants

- Personal libraries only.
- One request contains 1-50 objects.
- One persisted 32-character `Zotero-Write-Token` is bound to each exact batch payload.
- String-valued `success` and object-valued `successful` response maps are accepted and
  deduplicated by request index.
- `failed` and unexpected `unchanged` entries are handled by request index.
- Recognizable success keys are persisted before full normalization and reconciled by read-back.
- Missing dispositions are failures for only those indices when other success keys are known.
- Writes use no automatic transport retry.
- A timeout or lost response is an unknown outcome, never success.
- Every success key is fetched again. Only matching item type, normalized title, DOI when
  supplied, and collection placement yields `created_verified`.

## Collection creation invariants

- Preview performs no collection write. It stores the exact missing root collection name as an
  approval-bound creation intent.
- Commit verifies approval and writable user identity before collection creation.
- A persisted write token and `collection.state.json` bind the operation to the manifest.
- If the exact root name appears before commit or after an unknown network result, its key is
  reconciled and reused.
- The returned key is persisted before item creation and reused by resume.
- Existing items are never moved or added to the new collection.

## Status handling

| Status | Handling |
|---|---|
| `200` | Inspect every item-level disposition |
| `400` | Isolate the bad payload; do not retry automatically |
| `401` / `403` | Stop all writes and reconfigure permissions |
| `409` | Treat as locked; do not invent a new batch |
| `412` | Reconcile the persisted token and remote state |
| `413` | Internal batch-size defect |
| `429` | Respect Zotero rate-limit instructions |
| `5xx` | Report uncertain failure and reconcile before retry |

Official reference: <https://www.zotero.org/support/dev/web_api/v3/basics>
