"""CLI review command for HiveMind knowledge approval workflow.

Provides the `hivemind review` command that lets operators walk through
pending contributions, approve or reject them, and see gamification stats.

Design decisions (locked in research):
- Feel is POSITIVE and REWARDING — no scary PII warnings; users see clean content
- Users only see the already-PII-stripped version (no before/after comparison)
- Light gamification: contribution count + "helped X agents" after each approval
- Category override available during approval
- "Flag as sensitive" available if PII stripping missed something
- Sync DB client to avoid asyncio event loop issues with Typer

Usage:
    hivemind review --org-id <org_id> [--limit <n>]

    # Or set HIVEMIND_ORG_ID in the environment:
    export HIVEMIND_ORG_ID=acme-corp
    hivemind review
"""

from __future__ import annotations

import typer
import questionary
from rich.console import Console
from rich.panel import Panel

from hivemind.cli.client import (
    approve_contribution,
    compute_qi_score,
    fetch_pending,
    find_similar_knowledge,
    flag_contribution,
    get_org_stats,
    reject_contribution,
)
from hivemind.db.models import KnowledgeCategory

# Module-level console used by the review command
console = Console()


# ---------------------------------------------------------------------------
# TRUST-02 display helpers
# ---------------------------------------------------------------------------


def _build_similar_section(similar_items: list[dict]) -> str:
    """Build a Rich-formatted string for the similar knowledge section.

    Args:
        similar_items: List of dicts from find_similar_knowledge().

    Returns:
        A Rich markup string showing similar items or a 'none found' notice.
    """
    if not similar_items:
        return "\n[dim]No similar items in the commons yet.[/dim]"

    lines = ["\n[bold]Similar Existing Knowledge:[/bold]"]
    for item in similar_items:
        pct = item["similarity"]
        title = item["title"]
        category = item["category"]
        if pct >= 80:
            # Likely duplicate — highlight in yellow
            lines.append(
                f"  [yellow]{pct}% similar[/yellow] — {title} [{category}]"
            )
        else:
            lines.append(
                f"  [dim]{pct}% similar[/dim] — {title} [{category}]"
            )
    return "\n".join(lines)


def _build_qi_badge(qi: dict) -> str:
    """Build a Rich-formatted QI pre-screening badge string.

    Args:
        qi: Dict from compute_qi_score() with keys: score, label, color, icon, details.

    Returns:
        A Rich markup string with the badge on the first line and dim detail
        lines below (if any details exist).
    """
    color = qi["color"]
    badge_line = f"[{color}]QI: {qi['icon']} {qi['label']} ({qi['score']})[/{color}]"
    detail_lines = [f"[dim]  {d}[/dim]" for d in qi.get("details", [])]
    if detail_lines:
        return badge_line + "\n" + "\n".join(detail_lines)
    return badge_line


def review(
    org_id: str = typer.Option(
        ...,
        "--org-id",
        envvar="HIVEMIND_ORG_ID",
        help="Organisation ID to review pending contributions for.",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        help="Maximum number of contributions to review in this session.",
    ),
) -> None:
    """Review pending knowledge contributions and approve or reject them.

    Walks through each pending contribution in your organisation's review
    queue.  For each item you can:

    \b
    - Approve (private)        — publish to your org's private namespace only
    - Approve (public commons) — share with all connected orgs
    - Change category & approve — override the agent-suggested category
    - Flag as sensitive         — mark for re-examination (if PII was missed)
    - Reject                    — remove from the queue
    - Skip                      — leave for later

    After each approval, gamification stats are shown to encourage engagement.
    """
    # Fetch pending contributions
    pending = fetch_pending(org_id=org_id, limit=limit)

    # -----------------------------------------------------------------------
    # Empty queue — nothing to do
    # -----------------------------------------------------------------------
    if not pending:
        console.print(Panel(
            "[green]All caught up! No pending contributions.[/green]",
            title="HiveMind",
            border_style="green",
        ))
        return

    # -----------------------------------------------------------------------
    # Review loop
    # -----------------------------------------------------------------------
    console.print(f"\n[bold]You have {len(pending)} contribution(s) to review[/bold]\n")

    approved_count = 0
    rejected_count = 0
    flagged_count = 0
    skipped_count = 0

    for idx, item in enumerate(pending):
        # TRUST-02: Quality pre-screening signal
        qi = compute_qi_score(item)
        qi_badge = _build_qi_badge(qi)

        # TRUST-02: Similar existing knowledge lookup (graceful degradation on failure)
        try:
            similar_items = find_similar_knowledge(
                content=item.content,
                org_id=org_id,
                top_n=3,
                threshold=0.35,
            )
        except Exception:
            similar_items = []

        similar_section = _build_similar_section(similar_items)

        # Build display content
        meta_line = (
            f"[bold]{item.category.value}[/bold] · "
            f"Confidence: {item.confidence:.0%} · "
            f"{qi_badge}"
        )
        framework_line = ""
        if item.framework:
            framework_line += f"\n[dim]Framework: {item.framework}[/dim]"
        if item.language:
            framework_line += f"[dim] · Language: {item.language}[/dim]"

        panel_body = (
            f"{meta_line}\n\n"
            f"{item.content}\n"
            f"{similar_section}\n\n"
            f"[dim]Agent: {item.source_agent_id} · "
            f"{item.contributed_at.strftime('%Y-%m-%d %H:%M')}[/dim]"
            f"{framework_line}"
        )

        console.print(Panel(
            panel_body,
            title=f"Contribution {idx + 1}/{len(pending)}",
            border_style="blue",
        ))

        # Prompt action
        action = questionary.select(
            "What would you like to do?",
            choices=[
                "Approve (private)",
                "Approve (public commons)",
                "Change category & approve",
                "Flag as sensitive",
                "Reject",
                "Skip (review later)",
            ],
        ).ask()

        # Handle None (Ctrl+C or EOF)
        if action is None:
            console.print("\n[yellow]Review interrupted.[/yellow]")
            break

        # Handle each action
        if action == "Approve (private)":
            approve_contribution(item.id, is_public=False)
            approved_count += 1
            _show_gamification(org_id)

        elif action == "Approve (public commons)":
            approve_contribution(item.id, is_public=True)
            approved_count += 1
            _show_gamification(org_id)

        elif action == "Change category & approve":
            new_cat = questionary.select(
                "Choose category:",
                choices=[c.value for c in KnowledgeCategory],
            ).ask()

            if new_cat is None:
                console.print("[yellow]Category selection cancelled — skipping.[/yellow]")
                skipped_count += 1
                continue

            visibility = questionary.select(
                "Visibility:",
                choices=["Private", "Public commons"],
            ).ask()

            if visibility is None:
                console.print("[yellow]Visibility selection cancelled — skipping.[/yellow]")
                skipped_count += 1
                continue

            is_public = visibility == "Public commons"
            approve_contribution(item.id, is_public=is_public, category_override=new_cat)
            approved_count += 1
            _show_gamification(org_id)

        elif action == "Flag as sensitive":
            flag_contribution(item.id)
            flagged_count += 1
            console.print(
                "[yellow]Flagged for review. "
                "This contribution will be re-examined.[/yellow]\n"
            )

        elif action == "Reject":
            reject_contribution(item.id)
            rejected_count += 1
            console.print("[red]Rejected.[/red]\n")

        else:  # "Skip (review later)"
            skipped_count += 1

    # -----------------------------------------------------------------------
    # Session summary
    # -----------------------------------------------------------------------
    console.print(Panel(
        f"[bold green]Review session complete![/bold green]\n\n"
        f"Approved: {approved_count}\n"
        f"Rejected: {rejected_count}\n"
        f"Flagged:  {flagged_count}\n"
        f"Skipped:  {skipped_count}",
        title="Session Summary",
        border_style="green",
    ))


def _show_gamification(org_id: str) -> None:
    """Display a positive gamification message after an approval."""
    stats = get_org_stats(org_id)
    console.print(
        f"[green]Approved! "
        f"Your org has shared {stats['total_contributions']} piece(s) of knowledge "
        f"helping {stats['agent_count']} agent(s) learn faster.[/green]\n"
    )
