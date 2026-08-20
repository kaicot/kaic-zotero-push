"""Secure interactive prompts for CLI secrets."""

from getpass import getpass

import typer


def read_api_key() -> str:
    """Read a Zotero API key without displaying secret characters."""
    typer.echo("API 키를 붙여넣고 Enter를 누르세요. 보안을 위해 입력 문자는 표시되지 않습니다.")
    typer.echo(
        "PowerShell에서 Ctrl+V가 동작하지 않으면 마우스 오른쪽 버튼이나 Shift+Insert를 사용하세요."
    )
    api_key = getpass("Zotero API key: ")
    typer.echo("입력을 받았습니다. Zotero API 키와 권한을 확인하는 중입니다...")
    return api_key
