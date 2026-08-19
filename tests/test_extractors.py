import csv
from pathlib import Path

from openpyxl import Workbook

from kaic_zotero_push.extractors import extract_document


def test_extract_document_when_text_has_numbered_references(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "references.txt"
    content = """1. Smith, J. (2025). First title. Journal.
2. Lee, M. (2024). Second title. Journal.
"""
    _ = path.write_text(content, encoding="utf-8")

    # When
    extracted = extract_document(path)

    # Then
    assert len(extracted.candidates) == 2
    assert extracted.candidates[0].source_locator == "line=1"


def test_extract_document_when_csv_has_structured_columns(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "references.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["title", "author", "year", "doi"])
        writer.writeheader()
        writer.writerow(
            {
                "title": "A structured title",
                "author": "Smith, John",
                "year": "2025",
                "doi": "10.1000/csv",
            }
        )

    # When
    extracted = extract_document(path)

    # Then
    assert extracted.candidates[0].structured is not None
    assert extracted.candidates[0].structured.title == "A structured title"
    assert extracted.candidates[0].source_locator == "row=2"


def test_extract_document_when_xlsx_has_structured_columns(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "references.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["title", "author", "year", "doi"])
    sheet.append(["Spreadsheet title", "Kim, Hana", "2024", "10.1000/xlsx"])
    workbook.save(path)

    # When
    extracted = extract_document(path)

    # Then
    assert extracted.candidates[0].structured is not None
    assert extracted.candidates[0].structured.doi == "10.1000/xlsx"
    assert extracted.candidates[0].source_locator.endswith("row=2")
