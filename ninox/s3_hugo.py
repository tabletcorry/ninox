from __future__ import annotations

import datetime as dt
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

MIN_PARTS = 4

import boto3
import click

SHIPS = {
    "na": "Nieuw Amsterdam",
    "za": "Zaandam",
    "ko": "Koningsdam",
    "eu": "Eurodam",
    "rn": "Rotterdam",
    "ns": "Nieuw Statendam",
    "no": "Noordam",
    "os": "Oosterdam",
    "vo": "Volendam",
    "we": "Westerdam",
    "zu": "Zuiderdam",
}


def slug(name: str) -> str:
    """Convert a ship name to a slug suitable for paths."""
    return name.lower().replace(" ", "_")


def ensure_section(path: Path, title: str) -> None:
    """Ensure a Hugo section exists with an ``_index.md``."""
    path.mkdir(parents=True, exist_ok=True)
    index = path / "_index.md"
    if not index.exists():
        index.write_text(f"---\ntitle: {title}\n---\n")


def group_objects(bucket: str, prefix: str) -> dict[tuple[str, dt.date], list[str]]:
    """Group S3 object keys by ship code and date."""
    s3 = boto3.client("s3")
    paginator = s3.get_paginator("list_objects_v2")
    groups: dict[tuple[str, dt.date], list[str]] = defaultdict(list)
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            parts = key.split("/")
            if len(parts) < MIN_PARTS:
                continue
            ship_code = parts[1]
            if ship_code not in SHIPS:
                continue
            last_modified = obj["LastModified"].astimezone(dt.UTC).date()
            groups[ship_code, last_modified].append(key)
    return groups


def write_day_page(
    base: Path, ship_code: str, date: dt.date, keys: Iterable[str], cdn_host: str
) -> None:
    """Write an ``index.md`` listing ``keys`` for a single day."""
    ship_slug = slug(SHIPS[ship_code])
    day_dir = (
        base / "hal_menus" / ship_slug / f"{date:%Y}" / f"{date:%m}" / f"{date:%d}"
    )
    day_dir.mkdir(parents=True, exist_ok=True)
    lines = ["---", f"title: {date:%Y-%m-%d}", "---", ""]
    for key in keys:
        url = f"{cdn_host}/{key}"
        name = Path(key).name
        lines.append(f"- [{name}]({url})")
    (day_dir / "index.md").write_text("\n".join(lines))


def create_tree(bucket: str, prefix: str, output: Path, cdn_host: str) -> None:
    groups = group_objects(bucket, prefix)

    # Ensure section structure
    root = output / "hal_menus"
    ensure_section(root, "HAL Menus")
    for code in {code for code, _ in groups}:
        ship_name = SHIPS[code]
        ship_dir = root / slug(ship_name)
        ensure_section(ship_dir, ship_name)
        for date in {d for c, d in groups if c == code}:
            year_dir = ship_dir / f"{date:%Y}"
            ensure_section(year_dir, str(date.year))
            month_dir = year_dir / f"{date:%m}"
            ensure_section(month_dir, date.strftime("%B"))

    for (code, date), keys in groups.items():
        write_day_page(output, code, date, sorted(keys), cdn_host)


@click.command()
@click.option("--bucket", required=True, help="S3 bucket to scan")
@click.option("--prefix", default="content/", show_default=True, help="Key prefix")
@click.option(
    "--output",
    type=Path,
    default=Path("content"),
    show_default=True,
    help="Destination content directory",
)
@click.option("--cdn-host", required=True, help="Base URL for S3 objects")
def generate_menu_tree(bucket: str, prefix: str, output: Path, cdn_host: str) -> None:
    """Generate a Hugo content tree from menu PDFs stored in S3."""
    create_tree(bucket, prefix, output, cdn_host)


if __name__ == "__main__":
    generate_menu_tree()
