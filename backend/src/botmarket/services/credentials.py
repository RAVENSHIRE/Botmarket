"""Encryption of venue API credentials at rest.

A venue secret is a wallet private key or an exchange API secret — whoever holds
it can move the account's money. Three rules follow, and they are enforced here
rather than trusted to call sites:

1. **A secret is never stored in plaintext.** With no encryption key configured,
   :func:`seal` raises instead of falling back to storing it raw. Refusing to
   save is the safe failure; saving it unprotected is not.
2. **A secret is never returned.** Nothing in this module has a "get the secret
   for display" path. :func:`open_secret` exists to hand a key straight to a
   signing client and nowhere else.
3. **A secret is never logged.** The exceptions raised here quote the account
   and the problem, never the value — including when decryption fails, where
   the tempting thing to log is exactly the thing that must not be.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from botmarket.config import get_settings
from botmarket.domain.errors import InvalidAction


class CredentialError(InvalidAction):
    """A venue secret could not be sealed or opened."""


def generate_key() -> str:
    """Return a fresh Fernet key, for an operator to put in the environment."""
    return Fernet.generate_key().decode()


def _cipher() -> Fernet:
    """Return the configured cipher.

    Raises:
        CredentialError: If no encryption key is configured.
    """
    raw = get_settings().venue_encryption_key.strip()
    if not raw:
        raise CredentialError(
            "VENUE_ENCRYPTION_KEY is not set, so venue credentials cannot be "
            "stored. Generate one with `botmarket keygen` and add it to your "
            "environment. Paper trading needs no key."
        )
    try:
        return Fernet(raw.encode())
    except (ValueError, TypeError):
        # Accept a passphrase by deriving a valid Fernet key from it, so an
        # operator who set a plain string does not silently lose their data.
        digest = hashlib.sha256(raw.encode()).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def is_configured() -> bool:
    """Whether credentials can be stored at all in this deployment."""
    return bool(get_settings().venue_encryption_key.strip())


def seal(secret: str) -> str:
    """Encrypt ``secret`` for storage.

    Raises:
        CredentialError: If no encryption key is configured, or the secret is
            empty.
    """
    if not secret or not secret.strip():
        raise CredentialError("A venue secret cannot be empty")
    return _cipher().encrypt(secret.strip().encode()).decode()


def open_secret(sealed: str) -> str:
    """Decrypt a stored secret, for immediate use by a signing client.

    Raises:
        CredentialError: If the secret cannot be decrypted — usually because
            the encryption key changed since it was stored.
    """
    if not sealed:
        raise CredentialError("No credential is stored for this account")
    try:
        return _cipher().decrypt(sealed.encode()).decode()
    except InvalidToken as exc:
        raise CredentialError(
            "Stored credential could not be decrypted. This usually means "
            "VENUE_ENCRYPTION_KEY changed; re-link the account to fix it."
        ) from exc


def fingerprint(secret: str) -> str:
    """Return a short, non-reversible tag identifying a secret.

    Useful for confirming *which* key is loaded without revealing any of it —
    the only thing about a secret that is ever safe to show a user.
    """
    return hashlib.sha256(secret.encode()).hexdigest()[:8]
