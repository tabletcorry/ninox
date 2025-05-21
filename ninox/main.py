import click

from ninox import git_commands, image_description, s3_hugo
from ninox.config import load_config


@click.group()
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Base command group that loads configuration."""
    ctx.obj = load_config("~/.config/ninox/config.toml")


cli.add_command(image_description.describe_images)
cli.add_command(s3_hugo.generate_menu_tree)
cli.add_command(git_commands.git)
