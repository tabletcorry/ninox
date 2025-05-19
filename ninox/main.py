import click

from ninox import image_description, s3_hugo


@click.group()
def cli() -> None:
    pass


cli.add_command(image_description.describe_images)
cli.add_command(s3_hugo.generate_menu_tree)
