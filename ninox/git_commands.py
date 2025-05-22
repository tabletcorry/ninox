from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, cast

import click
from dulwich import porcelain
from dulwich.repo import Repo
from openai import OpenAI

if TYPE_CHECKING:
    from .config import Config


@click.group()
def git() -> None:
    """Git helper commands."""


@git.command()
@click.option(
    "--model", default="gpt-4.1-mini", show_default=True, help="OpenAI model to use"
)
@click.option(
    "-a",
    "--all",
    "stage_all",
    is_flag=True,
    help="Automatically stage tracked changes before committing.",
)
@click.option(
    "-n",
    "--dry-run",
    "dry_run",
    is_flag=True,
    help="Only print the suggested commit message and do not commit.",
)
@click.argument("paths", nargs=-1, type=click.Path())
@click.pass_obj
def commit(
    config: Config, model: str, stage_all: bool, dry_run: bool, paths: tuple[str, ...]
) -> None:
    """Generate a commit message with an LLM and commit staged changes."""
    repo = Repo(str(Path.cwd()))

    if stage_all and paths:
        raise click.UsageError("Cannot use -a with path arguments")

    if stage_all:
        tracked = [p.decode() for p in repo.open_index().paths()]  # type: ignore[no-untyped-call]
        if tracked:
            repo.stage(tracked)

    if paths:
        repo.stage(paths)

    index_tree = porcelain.write_tree(repo)  # type: ignore[no-untyped-call]
    try:
        head_tree = repo[b"HEAD"].tree
    except KeyError:
        head_tree = None
    diff_io = io.BytesIO()
    porcelain.diff_tree(repo.path, head_tree, index_tree, outstream=diff_io)
    patch = diff_io.getvalue().decode()
    if not patch.strip():
        click.echo("No staged changes to commit.")
        raise click.Abort

    client = OpenAI(api_key=config.tokens.openai.open)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are “CommitCraft AI”, an expert on the guidelines from"
                "A Note about Git Commit Messages” (tbaggery.com, 2008).",
            },
            {
                "role": "user",
                "content": f"""
Given ONLY the following git patch, create ONE commit message.

──────── PATCH START ────────
{patch}
──────── PATCH END ──────────

Format rules:
1. Subject line ≤ 50 chars, **imperative**, no period.
2. Exactly one blank line after the subject.
3. *Body wrapped ≤ 72 chars per line*; explain **what** & **why**, not how.
4. Mention high-level modules/files that changed, excluding lock files.
5. Further paragraphs start with a blank line; bulleted lists are OK.
6. Skip body for lock file updates.

Return only the formatted commit message—no code fences, no extra prose.""",
            },
        ],
        max_tokens=512,
    )
    message = cast("str", response.choices[0].message.content).strip()

    click.echo(f"Suggested commit message:\n{message}")
    if dry_run:
        return

    edited = click.edit(message)
    if edited is not None:
        message = edited.strip()

    porcelain.commit(repo.path, message=message)  # type: ignore[no-untyped-call]
    click.echo("Commit created.")
