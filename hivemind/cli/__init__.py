"""HiveMind CLI — manage your knowledge commons.

Entry point registered in pyproject.toml:
    hivemind = "hivemind.cli:app"

Commands:
    hivemind review   — review and approve/reject pending contributions

Usage:
    hivemind --help
    hivemind review --org-id <org_id>
    HIVEMIND_ORG_ID=acme-corp hivemind review
"""

import typer

from hivemind.cli.review import review

app = typer.Typer(
    name="hivemind",
    help="HiveMind CLI — manage your knowledge commons",
    no_args_is_help=True,
)

app.command()(review)
