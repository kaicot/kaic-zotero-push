"""Atomic run artifact persistence and preview rendering."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from kaic_zotero_push.errors import RunStateError
from kaic_zotero_push.models import Decision, JsonValue, Manifest


def create_run_directory(root: Path) -> Path:
    """Create a collision-resistant local run directory."""
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    run_dir = root / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    _ = temporary.write_text(content, encoding="utf-8")
    _ = temporary.replace(path)


def write_model(path: Path, model: BaseModel) -> None:
    """Atomically persist one Pydantic model."""
    _atomic_write(path, model.model_dump_json(indent=2, exclude_none=True))


def write_json(path: Path, value: JsonValue) -> None:
    """Atomically persist JSON without credentials or headers."""
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def write_text(path: Path, content: str) -> None:
    """Atomically persist a UTF-8 report."""
    _atomic_write(path, content)


def read_model[ModelT: BaseModel](path: Path, model_type: type[ModelT]) -> ModelT:
    """Read and validate one run model."""
    if not path.is_file():
        raise RunStateError(detail=f"Required run artifact is missing: {path.name}")
    try:
        return model_type.model_validate_json(path.read_bytes())
    except ValueError as error:
        raise RunStateError(detail=f"Run artifact is invalid: {path.name}") from error


def render_preview(manifest: Manifest) -> str:
    """Render the approval-facing Korean preview."""
    counts = dict.fromkeys(Decision, 0)
    for record in manifest.records:
        counts[record.decision] += 1
    target = manifest.target.collection_name or "라이브러리 루트"
    if manifest.target.create_collection:
        target = f"{target} (새 컬렉션 생성 예정)"
    lines = [
        "# Zotero 등록 미리보기",
        "",
        f"- 입력 문서: {Path(manifest.input_path).name}",
        f"- 발견: {len(manifest.records)}건",
        f"- 등록 예정: {counts[Decision.CREATE]}건",
        f"- 기존 중복: {counts[Decision.DUPLICATE_SKIPPED]}건",
        f"- 검토 필요: {counts[Decision.NEEDS_REVIEW]}건",
        f"- 파싱 실패: {counts[Decision.PARSE_FAILED]}건",
        f"- 대상: 개인 라이브러리 / {target}",
        "",
        "## 등록 예정 예시",
    ]
    for record in [item for item in manifest.records if item.decision is Decision.CREATE][:10]:
        identifier = f"DOI {record.parsed.doi}" if record.parsed.doi else "DOI 없음"
        description = f"{record.parsed.title} ({record.parsed.date or '연도 미상'}) / {identifier}"
        lines.append(f"{record.source.source_index}. [{record.parsed.item_type}] {description}")
    review_records = [item for item in manifest.records if item.decision is Decision.NEEDS_REVIEW][
        :10
    ]
    if review_records:
        lines.extend(["", "## 검토 필요 항목"])
        for record in review_records:
            warnings = ", ".join(record.quality.warnings)
            lines.append(f"- {record.source.source_index}. {record.parsed.title}: {warnings}")
    lines.extend(["", "**실제 등록은 아직 수행하지 않았습니다.**"])
    return "\n".join(lines) + "\n"
