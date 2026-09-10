"""Typer CLI used by agents and developers."""

import sys
from io import TextIOWrapper
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from kaic_zotero_push.approval import approve_manifest, verify_approval
from kaic_zotero_push.credentials import load_api_key, store_api_key
from kaic_zotero_push.destinations import describe_target
from kaic_zotero_push.errors import KaicZoteroPushError
from kaic_zotero_push.models import Approval, Manifest, OutcomeStatus
from kaic_zotero_push.pipeline import (
    CommitRequest,
    PreviewRequest,
    commit_run,
    prepare_run,
)
from kaic_zotero_push.prompts import read_api_key
from kaic_zotero_push.runs import read_model, write_model
from kaic_zotero_push.zotero.client import ZoteroClient


def _enable_utf8_console() -> None:
    if isinstance(sys.stdout, TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    if isinstance(sys.stderr, TextIOWrapper):
        sys.stderr.reconfigure(encoding="utf-8")


_enable_utf8_console()

app = typer.Typer(
    help="Preview and safely import document references into a Zotero personal library.",
    no_args_is_help=True,
)
console = Console(markup=False)
error_console = Console(stderr=True, markup=False)


@app.command()
def configure() -> None:
    """Validate and store a Zotero API key in Windows Credential Manager."""
    api_key = read_api_key()
    try:
        with ZoteroClient(api_key=api_key) as client:
            access = client.current_key()
        if not access.can_write:
            error_console.print("개인 라이브러리 쓰기 권한이 필요합니다.")
            raise typer.Exit(code=2)
        store_api_key(api_key)
    except KaicZoteroPushError as error:
        error_console.print(str(error))
        raise typer.Exit(code=2) from error
    console.print(f"설정 완료: {access.username} / userID={access.user_id} / 쓰기 가능")


@app.command()
def preview(  # noqa: PLR0913 -- Typer exposes each independent CLI option as a parameter.
    input_path: Annotated[Path, typer.Argument(help="Reference document path.")],
    *,
    collection: Annotated[
        str | None,
        typer.Option("--collection", help="Exact personal-library collection name."),
    ] = None,
    collection_key: Annotated[
        str | None, typer.Option("--collection-key", help="Explicit existing collection key.")
    ] = None,
    library_root: Annotated[
        bool, typer.Option("--library-root", help="Explicitly choose the library root.")
    ] = False,
    proposed_collection: Annotated[
        bool, typer.Option("--proposed-collection", help="Mark collection name as a proposal.")
    ] = False,
    offline: Annotated[
        bool,
        typer.Option("--offline", help="Parse locally without Zotero lookup or write."),
    ] = False,
    runs_dir: Annotated[
        Path | None,
        typer.Option("--runs-dir", help="Directory for local run artifacts."),
    ] = None,
) -> None:
    """Create a no-write preview and immutable manifest."""
    request = PreviewRequest(
        input_path=input_path,
        runs_dir=runs_dir or Path(".runs"),
        offline=offline,
        collection_name=collection,
        collection_key=collection_key,
        library_root=library_root,
        proposed_collection=proposed_collection,
    )
    try:
        request.validate_destination()
        if offline:
            prepared = prepare_run(request)
        else:
            with ZoteroClient(api_key=load_api_key()) as client:
                prepared = prepare_run(request, client)
    except KaicZoteroPushError as error:
        error_console.print(str(error))
        raise typer.Exit(code=2) from error
    console.print(prepared.preview)
    console.print(f"실행 폴더: {prepared.run_dir}")


@app.command()
def approve(
    run_dir: Annotated[Path, typer.Argument(help="Run directory shown by preview.")],
) -> None:
    """Record explicit approval for an unchanged preview."""
    try:
        manifest = read_model(run_dir / "manifest.json", Manifest)
        if manifest.target.user_id == 0:
            error_console.print("오프라인 미리보기는 실제 등록 승인을 만들 수 없습니다.")
            raise typer.Exit(code=2)
        approval_path = run_dir / "approval.json"
        if approval_path.is_file():
            verify_approval(manifest, read_model(approval_path, Approval))
        else:
            approval = approve_manifest(manifest)
            write_model(approval_path, approval)
    except KaicZoteroPushError as error:
        error_console.print(str(error))
        raise typer.Exit(code=2) from error
    target = describe_target(manifest.target)
    console.print(f"승인 기록 완료: userID={manifest.target.user_id}, collection={target}")


def _run_commit(run_dir: Path) -> None:
    try:
        with ZoteroClient(api_key=load_api_key()) as client:
            receipt = commit_run(CommitRequest(run_dir=run_dir), client)
    except KaicZoteroPushError as error:
        error_console.print(str(error))
        raise typer.Exit(code=2) from error
    counts = dict.fromkeys(OutcomeStatus, 0)
    for outcome in receipt.outcomes:
        counts[outcome.status] += 1
    console.print("Zotero 등록 결과")
    console.print(f"- 대상: {receipt.destination or '기존 영수증의 대상 기록 확인 필요'}")
    console.print(f"- 생성 및 검증 완료: {counts[OutcomeStatus.CREATED_VERIFIED]}건")
    console.print(f"- 기존 중복으로 제외: {counts[OutcomeStatus.DUPLICATE_SKIPPED]}건")
    console.print(f"- 검토 필요: {counts[OutcomeStatus.NEEDS_REVIEW]}건")
    console.print(f"- 파싱 실패: {counts[OutcomeStatus.PARSE_FAILED]}건")
    console.print(f"- 미시도: {counts[OutcomeStatus.NOT_ATTEMPTED]}건")
    console.print(
        f"- 실패: {counts[OutcomeStatus.WRITE_FAILED] + counts[OutcomeStatus.CREATED_UNVERIFIED]}건"
    )
    console.print(f"- 실행 영수증: {run_dir / 'receipt.json'}")
    console.print("검증 범위: 유형·제목·제공 DOI·컬렉션 배치 재조회. 출판 정보 대조는 미수행.")


@app.command(name="commit")
def commit_command(
    run_dir: Annotated[Path, typer.Argument(help="Approved run directory.")],
) -> None:
    """Create and verify approved Zotero items."""
    _run_commit(run_dir)


@app.command()
def resume(
    run_dir: Annotated[Path, typer.Argument(help="Partially completed run directory.")],
) -> None:
    """Re-evaluate a partial run before attempting remaining writes."""
    _run_commit(run_dir)
