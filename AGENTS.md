# Repository maintenance

These instructions cover development and release maintenance of kaic-zotero-push.
For reference-import execution, follow [SKILL.md](SKILL.md) and load only the relevant
supporting references; do not duplicate that workflow here.

## Scope and safety

- Keep changes within the user's approved scope. Documentation or release approval does not
  authorize live Zotero writes, credential reconfiguration, or unrelated library cleanup.
- Preserve preview approval, source/manifest/user/destination binding, destination-scoped
  duplicates, same-run recovery, and read-back verification unless explicitly approved to change.
- Never commit credentials, original documents, personal reference fixtures, or run artifacts.
  Keep `tests/`, `.runs/`, `.private/`, `private/`, and `.env*` excluded.
- Keep regression tests in the private local validation checkout. Do not force-add them to Git
  or include them in release archives. Missing tests in a public checkout are not passing tests.
- Use synthetic or mocked data for ordinary checks. Do not call `configure`, inspect saved keys,
  or use the production library as a test fixture. Live integration needs separate authorization.
- Preserve existing UI metadata and invocation policy in `agents/openai.yaml` unless a change
  is requested. This file is not a replacement for `agents/openai.yaml`.

## Versioning and release

Use the MAJOR.MINOR.PATCH policy documented in [README.md](README.md). Keep `VERSION`,
`pyproject.toml` project version, `src/kaic_zotero_push/__init__.py` version, the local project
entry in `uv.lock`, README current version, and CHANGELOG release heading/date aligned.
Do not upgrade dependencies just to synchronize a project version.

Before publishing:

1. Inspect local changes and remote branch/tag state. Preserve unrelated work.
2. Review the staged file list and diff for private files, credentials, and accidental changes.
3. Run the checks below and validate local Markdown links and version consistency.
4. Verify the source archive contains required skill documents and excludes private material.
5. When the user authorizes publication, commit the scoped changes and create an annotated
   `vX.Y.Z` tag at that commit. Push the branch and tag without force; use an atomic push where
   supported. Never move or replace a published tag.
6. Verify the remote branch and dereferenced tag point to the intended commit. Synchronize the
   local installed skill without overwriting unrelated modifications, then verify content and
   revision alignment.

Do not create a package-index publication or GitHub Release merely because a commit/push was
requested. Those are separate publication actions.

## Validation

Use a working project environment with locked dependencies. If the existing environment is
broken or in use, select an isolated `UV_PROJECT_ENVIRONMENT` rather than deleting it.

~~~powershell
uv sync --dev --locked
uv run pytest -q
uv run ruff format --check .
uv run ruff check .
uv run basedpyright --pythonpath "<active-environment>/Scripts/python.exe"
uv build --out-dir "<isolated-build-directory>"
~~~

Run pytest only where the private regression suite is present, with live network and credential
access blocked. Point basedpyright at the actual validation interpreter, especially when using
an isolated environment. Run the available skill frontmatter validator too; it checks structure,
not agent decision quality.

Report automated regressions, static/manual instruction review, and live integration separately.
Never describe mocked read-back or a help-command smoke test as production Zotero verification.
