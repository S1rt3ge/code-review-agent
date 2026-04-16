"""Tests for release workflow shell checks (policy parity)."""

import re


def _release_tag_valid(version: str) -> bool:
    return bool(re.fullmatch(r"^v[0-9]+\.[0-9]+\.[0-9]+$", version))


def test_release_tag_regex_accepts_semver_with_v_prefix() -> None:
    assert _release_tag_valid("v0.1.0")
    assert _release_tag_valid("v10.20.30")


def test_release_tag_regex_rejects_invalid_values() -> None:
    assert not _release_tag_valid("0.1.0")
    assert not _release_tag_valid("v0.1")
    assert not _release_tag_valid("v0.1.0-rc1")
