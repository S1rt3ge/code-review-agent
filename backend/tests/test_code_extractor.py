"""Tests for backend/services/code_extractor.py.

Covers:
    _language_from_filename: extension mapping
    _is_supported: extension allow-list
    extract_added_lines: (line_no, text) pairs
    _parse_patch: hunk → CodeChunk conversion
    extract_chunks: filtering (removed, no patch, unsupported extension)
"""

import pytest

from backend.services.code_extractor import (
    CodeChunk,
    _is_supported,
    _language_from_filename,
    _parse_patch,
    extract_added_lines,
    extract_chunks,
)
from backend.services.github_api import PullRequestFile


# ---------------------------------------------------------------------------
# _language_from_filename
# ---------------------------------------------------------------------------


def test_language_python():
    assert _language_from_filename("backend/app.py") == "python"


def test_language_typescript():
    assert _language_from_filename("src/App.tsx") == "typescript"


def test_language_unknown_no_extension():
    assert _language_from_filename("Makefile") == "unknown"


def test_language_unknown_unsupported_ext():
    assert _language_from_filename("image.png") == "unknown"


# ---------------------------------------------------------------------------
# _is_supported
# ---------------------------------------------------------------------------


def test_is_supported_python():
    assert _is_supported("app.py") is True


def test_is_supported_binary():
    assert _is_supported("logo.png") is False


def test_is_supported_no_extension():
    assert _is_supported("Dockerfile") is False


# ---------------------------------------------------------------------------
# extract_added_lines
# ---------------------------------------------------------------------------

SIMPLE_PATCH = (
    "@@ -1,3 +1,5 @@\n"
    " context line\n"
    "+added line one\n"
    "+added line two\n"
    " another context\n"
    "-removed line\n"
)


def test_extract_added_lines_returns_correct_pairs():
    result = extract_added_lines(SIMPLE_PATCH)
    assert result == [(2, "added line one"), (3, "added line two")]


def test_extract_added_lines_empty_patch():
    assert extract_added_lines("") == []


def test_extract_added_lines_no_additions():
    patch = "@@ -1,2 +1,2 @@\n context\n-removed\n"
    assert extract_added_lines(patch) == []


# ---------------------------------------------------------------------------
# _parse_patch → CodeChunk
# ---------------------------------------------------------------------------

MULTI_HUNK_PATCH = (
    "@@ -10,4 +10,5 @@\n"
    " ctx\n"
    "+new_line_a\n"
    " ctx2\n"
    "@@ -50,3 +51,4 @@\n"
    " base\n"
    "+new_line_b\n"
    " end\n"
)


def test_parse_patch_basic_chunk_fields():
    chunks = _parse_patch("src/app.py", SIMPLE_PATCH)
    assert len(chunks) >= 1
    chunk = chunks[0]
    assert chunk.filename == "src/app.py"
    assert chunk.language == "python"
    assert chunk.start_line == 1
    assert 2 in chunk.added_lines
    assert 3 in chunk.added_lines


def test_parse_patch_multi_hunk_produces_content():
    chunks = _parse_patch("service.py", MULTI_HUNK_PATCH)
    # Both hunks may be merged into one chunk or two; combined content must
    # contain both added lines.
    all_content = " ".join(c.content for c in chunks)
    assert "new_line_a" in all_content
    assert "new_line_b" in all_content


def test_parse_patch_added_lines_set():
    chunks = _parse_patch("mod.py", SIMPLE_PATCH)
    added = set()
    for c in chunks:
        added |= c.added_lines
    assert 2 in added
    assert 3 in added


def test_parse_patch_context_lines_not_in_added():
    chunks = _parse_patch("mod.py", SIMPLE_PATCH)
    added = set()
    for c in chunks:
        added |= c.added_lines
    # Line 1 is "context line" (not added)
    assert 1 not in added


# ---------------------------------------------------------------------------
# extract_chunks — integration-level filtering
# ---------------------------------------------------------------------------


def _make_file(filename, status="modified", patch=None):
    return PullRequestFile(
        filename=filename,
        status=status,
        additions=1,
        deletions=0,
        patch=patch,
    )


def test_extract_chunks_skips_removed_files():
    files = [_make_file("app.py", status="removed", patch=SIMPLE_PATCH)]
    assert extract_chunks(files) == []


def test_extract_chunks_skips_no_patch():
    files = [_make_file("image.png", patch=None)]
    assert extract_chunks(files) == []


def test_extract_chunks_skips_unsupported_extension():
    files = [_make_file("README.md", patch=SIMPLE_PATCH)]
    assert extract_chunks(files) == []


def test_extract_chunks_processes_supported_file():
    files = [_make_file("backend/app.py", patch=SIMPLE_PATCH)]
    chunks = extract_chunks(files)
    assert len(chunks) >= 1
    assert all(isinstance(c, CodeChunk) for c in chunks)


def test_extract_chunks_multiple_files():
    files = [
        _make_file("app.py", patch=SIMPLE_PATCH),
        _make_file("service.ts", patch=SIMPLE_PATCH),
        _make_file("photo.jpg", patch=None),
    ]
    chunks = extract_chunks(files)
    filenames = {c.filename for c in chunks}
    assert "app.py" in filenames
    assert "service.ts" in filenames
    # .jpg should be excluded entirely
    assert "photo.jpg" not in filenames
