"""Tests for release workflow policy parity helpers."""

import re


def _release_tag_valid(version: str) -> bool:
    return bool(re.fullmatch(r"^v[0-9]+\.[0-9]+\.[0-9]+$", version))


def _has_nonempty_unreleased_section(changelog: str) -> bool:
    lines = changelog.splitlines()
    found = False
    content = False
    for line in lines:
        if line.startswith("## [Unreleased]"):
            found = True
            continue
        if found and line.startswith("## ["):
            break
        if found and line.strip():
            content = True
    return found and content


def test_release_tag_regex_accepts_semver_with_v_prefix() -> None:
    assert _release_tag_valid("v0.1.0")
    assert _release_tag_valid("v10.20.30")


def test_release_tag_regex_rejects_invalid_values() -> None:
    assert not _release_tag_valid("0.1.0")
    assert not _release_tag_valid("v0.1")
    assert not _release_tag_valid("v0.1.0-rc1")


def test_changelog_requires_nonempty_unreleased_section() -> None:
    changelog = """# Changelog

## [Unreleased]

### Added
- New thing

## [2026-04-16]
"""
    assert _has_nonempty_unreleased_section(changelog)


def test_changelog_rejects_empty_unreleased_section() -> None:
    changelog = """# Changelog

## [Unreleased]

## [2026-04-16]
"""
    assert not _has_nonempty_unreleased_section(changelog)
