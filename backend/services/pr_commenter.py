"""PR comment formatter.

Converts aggregated findings and review metadata into a structured
GitHub PR comment in markdown format.

Functions:
    build_comment: Main entry point — produce the full comment body.
"""

from datetime import datetime, timezone
from decimal import Decimal

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]

SEVERITY_EMOJI: dict[str, str] = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🔵",
    "info": "⚪",
}

AGENT_EMOJI: dict[str, str] = {
    "security": "🔒",
    "performance": "⚡",
    "style": "✏️",
    "logic": "🧠",
}


def build_comment(
    findings: list[dict],
    agent_results: dict[str, dict] | None = None,
    estimated_cost: Decimal | None = None,
    pr_title: str | None = None,
    head_sha: str | None = None,
) -> str:
    """Build a GitHub PR comment body from review findings.

    Args:
        findings: Aggregated (deduplicated, ranked) list of finding dicts.
        agent_results: Per-agent execution metadata from the orchestrator.
        estimated_cost: Estimated USD cost for this review.
        pr_title: Pull request title for the header.
        head_sha: Head commit SHA (first 7 chars shown).

    Returns:
        Markdown string ready to POST to the GitHub issues/comments API.
    """
    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines.append("## 🤖 AI Code Review")
    if pr_title:
        lines.append(f"> {pr_title}")
    if head_sha:
        lines.append(f"> Commit: `{head_sha[:7]}`")
    lines.append("")

    # ── Summary bar ───────────────────────────────────────────────────────────
    non_dup = [f for f in findings if not f.get("is_duplicate")]
    counts: dict[str, int] = {}
    for f in non_dup:
        sev = f.get("severity", "info")
        counts[sev] = counts.get(sev, 0) + 1

    if not non_dup:
        lines.append("✅ **No issues found.** The code looks good!")
        lines.append("")
    else:
        summary_parts = []
        for sev in SEVERITY_ORDER:
            if sev in counts:
                summary_parts.append(f"{SEVERITY_EMOJI[sev]} {counts[sev]} {sev}")
        lines.append("**Summary:** " + "  ·  ".join(summary_parts))
        lines.append("")

        # ── Findings grouped by severity ──────────────────────────────────────
        by_severity: dict[str, list[dict]] = {}
        for f in non_dup:
            sev = f.get("severity", "info")
            by_severity.setdefault(sev, []).append(f)

        for sev in SEVERITY_ORDER:
            group = by_severity.get(sev, [])
            if not group:
                continue

            emoji = SEVERITY_EMOJI[sev]
            lines.append(f"### {emoji} {sev.capitalize()} ({len(group)})")
            lines.append("")

            for f in group:
                file_path = f.get("file_path", "unknown")
                line_no = f.get("line_number", 0)
                agent = f.get("agent_name", "agent")
                ftype = f.get("finding_type", "issue")
                message = f.get("message", "")
                suggestion = f.get("suggestion")
                snippet = f.get("code_snippet")
                agent_icon = AGENT_EMOJI.get(agent, "🔍")

                lines.append(
                    f"**`{file_path}:{line_no}`** "
                    f"<sub>{agent_icon} {agent} / {ftype}</sub>"
                )
                lines.append(f"> {message}")
                if suggestion:
                    lines.append(f">\n> 💡 **Fix:** {suggestion}")
                if snippet:
                    lines.append(f"\n```\n{snippet}\n```")
                lines.append("")

    # ── Agent execution summary ────────────────────────────────────────────────
    if agent_results:
        lines.append("<details>")
        lines.append("<summary>Agent details</summary>")
        lines.append("")
        lines.append("| Agent | Status | Findings | Tokens |")
        lines.append("|-------|--------|----------|--------|")

        for agent_name, meta in sorted(agent_results.items()):
            icon = AGENT_EMOJI.get(agent_name, "🔍")
            st = meta.get("status", "?")
            status_icon = "✅" if st == "done" else "❌"
            fc = meta.get("findings_count", 0)
            tokens = meta.get("tokens_input", 0) + meta.get("tokens_output", 0)
            err = meta.get("error_message")

            row = f"| {icon} {agent_name} | {status_icon} {st} | {fc} | {tokens:,} |"
            if err:
                row += f" _{err[:60]}_"
            lines.append(row)

        lines.append("")
        lines.append("</details>")
        lines.append("")

    # ── Footer ────────────────────────────────────────────────────────────────
    footer_parts: list[str] = []
    total_non_dup = len(non_dup)
    dup_count = len(findings) - total_non_dup
    footer_parts.append(f"{total_non_dup} finding{'s' if total_non_dup != 1 else ''}")
    if dup_count:
        footer_parts.append(f"{dup_count} duplicate{'s' if dup_count != 1 else ''} hidden")
    if estimated_cost is not None and estimated_cost > 0:
        footer_parts.append(f"~${estimated_cost:.4f}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines.append(f"---")
    lines.append(f"*{' · '.join(footer_parts)} · {now}*")

    return "\n".join(lines)
