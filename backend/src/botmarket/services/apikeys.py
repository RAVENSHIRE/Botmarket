"""Per-agent API keys.

Every write endpoint is scoped to an agent, and since an agent can now move real
money, "which agent is calling?" has to be answered by a credential rather than
by a path parameter anyone can type.

The rules mirror the venue credential store, for the same reasons:

* **The key is shown once.** Only a hash is stored, so a lost key is reissued,
  never recovered. There is no endpoint that returns one.
* **Comparison is constant-time.** A timing-variable compare on a secret is a
  slow leak of that secret.
* **A visible prefix is kept for display.** Operators need to tell two keys
  apart without seeing either in full.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

#: Marks a Botmarket key in logs and config files.
KEY_PREFIX = "bmk"

#: Bytes of entropy. 32 bytes is ~256 bits — far past guessing.
KEY_BYTES = 32

#: How much of the key is stored in clear for display.
DISPLAY_CHARS = 8


def generate() -> tuple[str, str, str]:
    """Mint a key.

    Returns:
        ``(key, key_hash, display_prefix)``. The caller must show ``key`` to its
        owner exactly once and persist only the other two.
    """
    key = f"{KEY_PREFIX}_{secrets.token_urlsafe(KEY_BYTES)}"
    return key, hash_key(key), key[: len(KEY_PREFIX) + 1 + DISPLAY_CHARS]


def hash_key(key: str) -> str:
    """Return the stored form of ``key``.

    A plain SHA-256 rather than a password hash is the right call here: an API
    key is 256 bits of machine-generated entropy, so there is no dictionary to
    attack and the slow-hash cost would buy nothing but latency on every
    request.
    """
    return hashlib.sha256(key.strip().encode()).hexdigest()


def matches(key: str, stored_hash: str) -> bool:
    """Whether ``key`` is the key behind ``stored_hash``, compared safely."""
    if not key or not stored_hash:
        return False
    return hmac.compare_digest(hash_key(key), stored_hash)


def extract(authorization: str | None, api_key_header: str | None) -> str | None:
    """Pull a key out of the request headers.

    Both ``Authorization: Bearer <key>`` and ``X-API-Key: <key>`` are accepted —
    the first is what HTTP tooling expects, the second is what a five-line shell
    agent will actually send.
    """
    if api_key_header and api_key_header.strip():
        return api_key_header.strip()
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None
