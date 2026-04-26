"""Unified diff parser that converts PR file patches into structured code chunks.

Classes:
    CodeChunk: A contiguous block of added lines from a unified diff.

Functions:
    extract_chunks: Parse PullRequestFile objects into CodeChunk objects.
    extract_added_lines: Extract added line numbers and text from a patch string.
"""

import re
from dataclasses import dataclass, field

from backend.services.github_api import PullRequestFile

# Heuristic: only extract files whose extension matches these languages.
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py", ".js", ".jsx", ".ts", ".tsx",
        ".java", ".go", ".rb", ".rs", ".cs",
        ".cpp", ".c", ".h", ".php", ".swift",
        ".kt", ".scala", ".sh", ".yaml", ".yml",
        ".json", ".toml", ".sql",
    }
)

# Maximum characters per chunk to stay within LLM context limits.
MAX_CHUNK_CHARS = 8_000

# Regex to match unified diff hunk headers: @@ -a,b +c,d @@
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


@dataclass
class CodeChunk:
    """A contiguous block of changed lines from a single file.

    Attributes:
        filename: Path of the file relative to the repo root.
        language: Detected language (from file extension, lower-case).
        start_line: First line number in the *new* file (1-based).
        end_line: Last line number in the *new* file (1-based).
        content: The chunk text (added + context lines, no diff markers).
        added_lines: Set of line numbers that are new (i.e. were added).
    """

    filename: str
    language: str
    start_line: int
    end_line: int
    content: str
    added_lines: set[int] = field(default_factory=set)


def _language_from_filename(filename: str) -> str:
    """Derive a language identifier from a file extension.

    Args:
        filename: File path, e.g. ``src/app.py``.

    Returns:
        Lower-case language string, e.g. ``python``, or ``unknown``.
    """
    ext_map: dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".rb": "ruby",
        ".rs": "rust",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".php": "php",
        ".swift": "swift",
        ".kt": "kotlin",
        ".scala": "scala",
        ".sh": "bash",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".toml": "toml",
        ".sql": "sql",
    }
    dot_pos = filename.rfind(".")
    if dot_pos == -1:
        return "unknown"
    return ext_map.get(filename[dot_pos:].lower(), "unknown")


def _is_supported(filename: str) -> bool:
    """Return True if the file extension is in SUPPORTED_EXTENSIONS."""
    dot_pos = filename.rfind(".")
    if dot_pos == -1:
        return False
    return filename[dot_pos:].lower() in SUPPORTED_EXTENSIONS


def _parse_patch(filename: str, patch: str) -> list[CodeChunk]:
    """Convert a unified diff patch string into CodeChunk objects.

    Hunks that exceed MAX_CHUNK_CHARS are split at hunk boundaries so each
    chunk stays within the size limit.

    Args:
        filename: File path for metadata.
        patch: Unified diff string from the GitHub API ``patch`` field.

    Returns:
        List of CodeChunk objects, one per logical block.
    """
    language = _language_from_filename(filename)
    chunks: list[CodeChunk] = []

    # Accumulate lines for the current hunk window.
    current_lines: list[str] = []
    current_start: int = 1
    current_line_no: int = 1
    added_in_current: set[int] = set()

    def _flush() -> None:
        nonlocal current_lines, current_start, added_in_current
        if not current_lines:
            return
        content = "\n".join(current_lines)
        end_line = current_start + len(current_lines) - 1
        chunks.append(
            CodeChunk(
                filename=filename,
                language=language,
                start_line=current_start,
                end_line=end_line,
                content=content,
                added_lines=set(added_in_current),
            )
        )
        current_lines = []
        added_in_current = set()

    for raw_line in patch.splitlines():
        hunk_match = _HUNK_HEADER.match(raw_line)
        if hunk_match:
            hunk_start = int(hunk_match.group(1))
            # Keep hunk line ranges precise; merging distant hunks makes LLM
            # line references ambiguous and hurts inline finding accuracy.
            if current_lines:
                _flush()
            current_start = hunk_start
            current_line_no = hunk_start
            continue

        if raw_line.startswith("+"):
            text = raw_line[1:]  # strip leading '+'
            current_lines.append(text)
            added_in_current.add(current_line_no)
            current_line_no += 1
        elif raw_line.startswith("-"):
            # Deleted lines don't appear in new file; skip line number advance.
            pass
        else:
            # Context line (space prefix or bare).
            text = raw_line[1:] if raw_line.startswith(" ") else raw_line
            current_lines.append(text)
            current_line_no += 1

    _flush()
    return chunks


def extract_added_lines(patch: str) -> list[tuple[int, str]]:
    """Return (line_number, text) pairs for every added line in a patch.

    Useful for building inline comment payloads that target specific lines.

    Args:
        patch: Unified diff string from the GitHub API.

    Returns:
        List of (new_file_line_number, line_text) for added lines only.
    """
    result: list[tuple[int, str]] = []
    line_no = 1

    for raw_line in patch.splitlines():
        hunk_match = _HUNK_HEADER.match(raw_line)
        if hunk_match:
            line_no = int(hunk_match.group(1))
            continue

        if raw_line.startswith("+"):
            result.append((line_no, raw_line[1:]))
            line_no += 1
        elif raw_line.startswith("-"):
            pass  # deleted — no new-file line number
        else:
            line_no += 1

    return result


def extract_chunks(files: list[PullRequestFile]) -> list[CodeChunk]:
    """Convert a list of PR files into structured CodeChunk objects.

    Skips files that:
    - Have no patch (binary files, files exceeding GitHub's diff size limit).
    - Have an unsupported file extension.
    - Were removed (status == "removed").

    Args:
        files: List of PullRequestFile from ``GitHubApiClient.get_pr_files``.

    Returns:
        Flat list of CodeChunk objects across all supported changed files.
    """
    chunks: list[CodeChunk] = []
    for f in files:
        if f.status == "removed":
            continue
        if not f.patch:
            continue
        if not _is_supported(f.filename):
            continue
        chunks.extend(_parse_patch(f.filename, f.patch))
    return chunks
