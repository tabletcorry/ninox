# ruff: noqa: S101
import datetime as dt
from collections.abc import Iterable
from pathlib import Path

import pytest

from ninox import s3_hugo


def test_slug() -> None:
    assert s3_hugo.slug("Nieuw Amsterdam") == "nieuw_amsterdam"


def test_ensure_section(tmp_path: Path) -> None:
    section = tmp_path / "foo"
    s3_hugo.ensure_section(section, "Foo")
    assert (section / "_index.md").read_text() == "---\ntitle: Foo\n---\n"
    # second call should not fail or change content
    s3_hugo.ensure_section(section, "Foo")
    assert (section / "_index.md").read_text() == "---\ntitle: Foo\n---\n"


def test_group_objects(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePaginator:
        @staticmethod
        def paginate(bucket: str, prefix: str) -> Iterable[dict[str, list[dict]]]:
            assert bucket == "my-bucket"
            assert prefix == "content/"
            yield {
                "Contents": [
                    {
                        "Key": "content/ko/menu/abc/file.pdf",
                        "LastModified": dt.datetime(2025, 3, 17, tzinfo=dt.UTC),
                    },
                    {
                        "Key": "content/na/menu/def/file2.pdf",
                        "LastModified": dt.datetime(2025, 3, 18, tzinfo=dt.UTC),
                    },
                    {
                        "Key": "invalid",
                        "LastModified": dt.datetime(2025, 3, 19, tzinfo=dt.UTC),
                    },
                    {
                        "Key": "content/xx/menu/ghi/file3.pdf",
                        "LastModified": dt.datetime(2025, 3, 20, tzinfo=dt.UTC),
                    },
                ]
            }

    class FakeClient:
        @staticmethod
        def get_paginator(name: str) -> FakePaginator:
            assert name == "list_objects_v2"
            return FakePaginator()

    monkeypatch.setattr(s3_hugo.boto3, "client", lambda _service: FakeClient())

    groups = s3_hugo.group_objects("my-bucket", "content/")

    assert groups == {
        ("ko", dt.date(2025, 3, 17)): ["content/ko/menu/abc/file.pdf"],
        ("na", dt.date(2025, 3, 18)): ["content/na/menu/def/file2.pdf"],
    }


def test_write_day_page(tmp_path: Path) -> None:
    date = dt.date(2025, 3, 17)
    key = "content/ko/menu/abc/file.pdf"
    s3_hugo.write_day_page(tmp_path, "ko", date, [key], "https://cdn")
    index = (
        tmp_path
        / "hal_menus"
        / "koningsdam"
        / "2025"
        / "03"
        / "17"
        / "index.md"
    )
    content = index.read_text()
    assert "title: 2025-03-17" in content
    assert "- [file.pdf](https://cdn/content/ko/menu/abc/file.pdf)" in content


def test_create_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    groups = {
        ("ko", dt.date(2025, 3, 17)): ["content/ko/menu/abc/file.pdf"],
        ("ko", dt.date(2025, 3, 18)): ["content/ko/menu/def/file2.pdf"],
        ("na", dt.date(2025, 3, 19)): ["content/na/menu/ghi/file3.pdf"],
    }

    monkeypatch.setattr(s3_hugo, "group_objects", lambda _bucket, _prefix: groups)

    s3_hugo.create_tree("my-bucket", "content/", tmp_path, "https://cdn")

    root = tmp_path / "hal_menus"
    assert (root / "_index.md").exists()
    ship_dir = root / "koningsdam"
    assert (ship_dir / "_index.md").exists()
    year_dir = ship_dir / "2025"
    assert (year_dir / "_index.md").exists()
    month_dir = year_dir / "03"
    assert (month_dir / "_index.md").exists()
    day_index = month_dir / "17" / "index.md"
    assert day_index.exists()
    assert "file.pdf" in day_index.read_text()
