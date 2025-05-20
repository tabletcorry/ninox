from __future__ import annotations

import io
from pathlib import Path
from typing import cast

import click
from dulwich import porcelain
from dulwich.repo import Repo
from openai import OpenAI

from .config import load_config


@click.group()
def git() -> None:
    """Git helper commands."""


@git.command()
@click.option(
    "--model", default="gpt-4.1-nano", show_default=True, help="OpenAI model to use"
)
def commit(model: str) -> None:
    """Generate a commit message with an LLM and commit staged changes."""
    repo = Repo(str(Path.cwd()))
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

    config = load_config("~/.config/ninox/config.toml")
    client = OpenAI(api_key=config.tokens.openai.open)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Write a concise git commit message in the imperative mood.",
            },
            {"role": "user", "content": f"Patch:\n{patch}"},
        ],
        max_tokens=50,
    )
    message = cast("str", response.choices[0].message.content).strip()

    click.echo(f"Suggested commit message:\n{message}")
    if click.confirm("Edit commit message?", default=False):
        edited = click.edit(message)
        if edited is not None:
            message = edited.strip()

    porcelain.commit(repo.path, message=message)  # type: ignore[no-untyped-call]
    click.echo("Commit created.")
