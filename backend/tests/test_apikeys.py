"""Tests for the API-key primitives.

These are the pieces an authentication bug hides in: how a key is compared, what
a header parser accepts, and whether anything leaks the secret back out.
"""

from __future__ import annotations

from botmarket.services import apikeys


def test_a_generated_key_is_prefixed_and_long():
    key, _, _ = apikeys.generate()
    assert key.startswith(f"{apikeys.KEY_PREFIX}_")
    # 32 bytes base64url-encoded, so comfortably past guessing.
    assert len(key) > 40


def test_keys_are_unique():
    keys = {apikeys.generate()[0] for _ in range(100)}
    assert len(keys) == 100


def test_the_stored_form_is_not_the_key():
    key, key_hash, prefix = apikeys.generate()
    assert key_hash != key
    assert key not in key_hash
    # The display prefix is a fragment, not enough to reconstruct anything.
    assert key.startswith(prefix)
    assert len(prefix) < len(key)


def test_matching_accepts_the_right_key_and_rejects_others():
    key, key_hash, _ = apikeys.generate()
    other, _, _ = apikeys.generate()

    assert apikeys.matches(key, key_hash)
    assert not apikeys.matches(other, key_hash)


def test_matching_is_safe_with_empty_input():
    _, key_hash, _ = apikeys.generate()
    assert not apikeys.matches("", key_hash)
    assert not apikeys.matches("anything", "")


def test_hashing_is_stable_and_whitespace_tolerant():
    key, key_hash, _ = apikeys.generate()
    assert apikeys.hash_key(key) == key_hash
    assert apikeys.hash_key(f"  {key}  ") == key_hash


def test_the_bearer_header_is_parsed():
    assert apikeys.extract("Bearer abc123", None) == "abc123"
    assert apikeys.extract("bearer abc123", None) == "abc123"


def test_the_api_key_header_is_parsed():
    assert apikeys.extract(None, "abc123") == "abc123"
    assert apikeys.extract(None, "  abc123  ") == "abc123"


def test_the_explicit_header_wins_over_bearer():
    assert apikeys.extract("Bearer from-bearer", "from-header") == "from-header"


def test_nothing_usable_yields_none():
    for authorization, header in (
        (None, None),
        ("", ""),
        ("Basic dXNlcjpwYXNz", None),
        ("Bearer ", None),
        ("Bearer", None),
    ):
        assert apikeys.extract(authorization, header) is None
