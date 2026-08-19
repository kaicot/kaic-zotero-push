"""Windows Credential Manager backed Zotero key storage."""

import keyring
from keyring.errors import KeyringError

from kaic_zotero_push.errors import CredentialError

_SERVICE = "kaic-zotero-push"
_ACCOUNT = "zotero-api-key"


def store_api_key(api_key: str) -> None:
    """Store a validated key without writing project files."""
    if not api_key.strip():
        raise CredentialError(detail="The Zotero API key cannot be empty.")
    try:
        keyring.set_password(_SERVICE, _ACCOUNT, api_key.strip())
    except KeyringError as error:
        raise CredentialError(detail="Windows Credential Manager rejected the key.") from error


def load_api_key() -> str:
    """Load the configured key without displaying it."""
    try:
        api_key = keyring.get_password(_SERVICE, _ACCOUNT)
    except KeyringError as error:
        raise CredentialError(detail="Could not read Windows Credential Manager.") from error
    if not api_key:
        raise CredentialError(
            detail="No Zotero API key is configured. Run `kaic-zotero-push configure`."
        )
    return api_key
