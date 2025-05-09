import click

from ninox import image_description


@click.group()
def cli() -> None:
    pass


cli.add_command(image_description.describe_images)
