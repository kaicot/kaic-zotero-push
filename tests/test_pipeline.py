from pathlib import Path

from docx import Document
from typer.testing import CliRunner

from kaic_zotero_push.cli import app
from kaic_zotero_push.models import Decision, Manifest
from kaic_zotero_push.runs import read_model


def test_preview_when_offline_text_input_is_valid(tmp_path: Path) -> None:
    # Given
    source = Path(__file__).parent / "fixtures" / "references.txt"
    runs_dir = tmp_path / "runs"
    runner = CliRunner()

    # When
    result = runner.invoke(
        app,
        ["preview", str(source), "--offline", "--runs-dir", str(runs_dir)],
    )

    # Then
    assert result.exit_code == 0
    run_directories = list(runs_dir.iterdir())
    assert len(run_directories) == 1
    assert (run_directories[0] / "manifest.json").exists()
    assert (run_directories[0] / "preview.md").exists()


def test_preview_when_input_extension_is_unsupported(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "references.rtf"
    _ = path.write_text("not supported", encoding="utf-8")
    runner = CliRunner()

    # When
    result = runner.invoke(app, ["preview", str(path), "--offline"])

    # Then
    assert result.exit_code == 2


def test_preview_when_docx_reference_boundary_is_unconfirmed_requires_review(
    tmp_path: Path,
) -> None:
    # Given
    source = tmp_path / "unbounded.docx"
    document = Document()
    doi_url = "https://doi.org/10.1000/unbounded"
    _ = document.add_paragraph(
        f"Smith, J. (2025). A complete article. Journal of Testing. {doi_url}"
    )
    document.save(str(source))
    runs_dir = tmp_path / "runs"

    # When
    result = CliRunner().invoke(
        app,
        ["preview", str(source), "--offline", "--runs-dir", str(runs_dir)],
    )

    # Then
    assert result.exit_code == 0
    run_dir = next(runs_dir.iterdir())
    manifest = read_model(run_dir / "manifest.json", Manifest)
    assert manifest.records[0].decision is Decision.NEEDS_REVIEW
    assert "unconfirmed_reference_section" in manifest.records[0].quality.warnings


def test_preview_when_metadata_is_missing_displays_warning_codes(tmp_path: Path) -> None:
    # Given
    source = tmp_path / "weak.txt"
    _ = source.write_text(
        "A title with no authors or journal. https://doi.org/10.1000/weak",
        encoding="utf-8",
    )
    runs_dir = tmp_path / "runs"

    # When
    result = CliRunner().invoke(
        app,
        ["preview", str(source), "--offline", "--runs-dir", str(runs_dir)],
    )

    # Then
    assert result.exit_code == 0
    preview = (next(runs_dir.iterdir()) / "preview.md").read_text(encoding="utf-8")
    assert "missing_creators" in preview
    assert "missing_publication_title" in preview
