from pathlib import Path

from typer.testing import CliRunner

from kaic_zotero_push.cli import app


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
