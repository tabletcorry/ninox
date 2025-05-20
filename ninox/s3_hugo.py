from __future__ import annotations

import datetime as dt
import re
import tomllib
from collections import defaultdict
from pathlib import Path

import boto3
import click
from pydantic import BaseModel

MIN_PARTS = 4

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

MD5_PREFIX = re.compile(r"^[0-9a-f]{32}[-_]")

# Default name for ship description configuration files
DEFAULT_CONFIG = Path("config.toml")


class ShipConfig(BaseModel):
    """Configuration data loaded from TOML."""

    ships: dict[str, str] = {}


def load_ship_config(config_path: Path | str) -> ShipConfig:
    """Load ship descriptions from a TOML file."""
    path = Path(config_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("rb") as f:
        data = tomllib.load(f)
    return ShipConfig(**data)


def strip_md5_prefix(name: str) -> str:
    """Remove an MD5 prefix from ``name`` if present."""
    return MD5_PREFIX.sub("", name)


def slug(name: str) -> str:
    """Convert a ship name to a slug suitable for paths."""
    return name.lower().replace(" ", "_")


def ensure_section(path: Path, title: str, description: str | None = None) -> None:
    """Ensure a Hugo section exists with an ``_index.md``."""
    path.mkdir(parents=True, exist_ok=True)
    index = path / "_index.md"
    if not index.exists():
        lines = [
            "---",
            f"title: {title}",
            "ShowReadingTime: false",
            "hideMeta: true",
            "hideSummary: true",
            "hiddenInHomeList: true",
        ]
        if description:
            lines.append(f"description: {description}")
        lines.append("---")
        index.write_text("\n".join(lines) + "\n")


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


def write_year_page(  # noqa: PLR0913
    base: Path,
    ship_code: str,
    year: int,
    days: dict[dt.date, list[str]],
    cdn_host: str,
    *,
    description: str | None = None,
) -> None:
    """Write an ``index.md`` listing all menus for ``year`` grouped by month."""
    ship_slug = slug(SHIPS[ship_code])
    year_dir = base / "hal_menus" / ship_slug / f"{year}"
    year_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        "---",
        f"title: {year}",
        "ShowReadingTime: false",
        "hideMeta: true",
        "hideSummary: true",
        "hiddenInHomeList: true",
    ]
    if description:
        lines.append(f"description: {description} - {year}")
    lines.extend(["---", ""])

    month_map: dict[int, dict[dt.date, list[str]]] = defaultdict(dict)
    for date, keys in days.items():
        month_map[date.month][date] = keys

    for month in sorted(month_map):
        month_name = dt.date(year, month, 1).strftime("%B")
        lines.extend((f'{{{{< details title="{month_name}" >}}}}', ""))
        for date in sorted(month_map[month]):
            lines.append(f"### {date:%Y-%m-%d}")
            for key in sorted(month_map[month][date]):
                url = f"{cdn_host}/{key}"
                name = strip_md5_prefix(Path(key).name)
                lines.append(f"- [{name}]({url})")
            lines.append("")
        lines.extend(("{{< /details >}}", ""))

    (year_dir / "index.md").write_text("\n".join(lines))


def create_tree(
    bucket: str,
    prefix: str,
    output: Path,
    cdn_host: str,
    config_path: Path | None = None,
) -> None:
    groups = group_objects(bucket, prefix)
    descriptions: dict[str, str] = {}
    if config_path:
        descriptions = load_ship_config(config_path).ships

    # Ensure section structure
    root = output / "hal_menus"
    ensure_section(root, "HAL Menus")
    for code in {code for code, _ in groups}:
        ship_name = SHIPS[code]
        ship_dir = root / slug(ship_name)
        ensure_section(ship_dir, ship_name, descriptions.get(code))

    year_groups: dict[tuple[str, int], dict[dt.date, list[str]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for (code, date), keys in groups.items():
        year_groups[code, date.year][date].extend(sorted(keys))

    for (code, year), days in year_groups.items():
        write_year_page(
            output, code, year, days, cdn_host, description=descriptions.get(code)
        )


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
@click.option("--config", type=Path, help="TOML config file with ship descriptions")
def generate_menu_tree(
    bucket: str, prefix: str, output: Path, cdn_host: str, config: Path | None = None
) -> None:
    """Generate a Hugo content tree from menu PDFs stored in S3."""
    if config is None:
        candidate = Path.cwd() / DEFAULT_CONFIG
        if candidate.is_file():
            config = candidate
        elif not click.confirm(
            "No config.toml file found. Continue without ship descriptions?",
            default=True,
        ):
            raise click.Abort

    create_tree(bucket, prefix, output, cdn_host, config)


if __name__ == "__main__":
    generate_menu_tree()
