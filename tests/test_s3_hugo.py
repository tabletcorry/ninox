# ruff: noqa: S101
import datetime as dt
from collections.abc import Iterable
from pathlib import Path

import pytest

from ninox import s3_hugo


def test_strip_md5_prefix() -> None:
    prefix = "a" * 32
    assert s3_hugo.strip_md5_prefix(f"{prefix}-file.pdf") == "file.pdf"
    assert s3_hugo.strip_md5_prefix(f"{prefix}_file.pdf") == "file.pdf"
    assert s3_hugo.strip_md5_prefix("file.pdf") == "file.pdf"


def test_slug() -> None:
    assert s3_hugo.slug("Nieuw Amsterdam") == "nieuw_amsterdam"


def test_ensure_section(tmp_path: Path) -> None:
    section = tmp_path / "foo"
    s3_hugo.ensure_section(section, "Foo")
    assert (
        section / "_index.md"
    ).read_text() == "---\ntitle: Foo\nhiddenInHomeList: true\n---\n"
    # second call should not fail or change content
    s3_hugo.ensure_section(section, "Foo")
    assert (
        section / "_index.md"
    ).read_text() == "---\ntitle: Foo\nhiddenInHomeList: true\n---\n"


def test_group_objects(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePaginator:
        @staticmethod
        def paginate(**kwargs: object) -> Iterable[dict[str, list[dict[str, object]]]]:
            assert kwargs["Bucket"] == "my-bucket"
            assert kwargs["Prefix"] == "content/"
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

    monkeypatch.setattr(s3_hugo.boto3, "client", lambda _service: FakeClient())  # type: ignore[attr-defined]

    groups = s3_hugo.group_objects("my-bucket", "content/")

    assert groups == {
        ("ko", dt.date(2025, 3, 17)): ["content/ko/menu/abc/file.pdf"],
        ("na", dt.date(2025, 3, 18)): ["content/na/menu/def/file2.pdf"],
    }


def test_write_day_page(tmp_path: Path) -> None:
    date = dt.date(2025, 3, 17)
    prefix = "a" * 32
    key = f"content/ko/menu/abc/{prefix}-file.pdf"
    s3_hugo.write_day_page(tmp_path, "ko", date, [key], "https://cdn")
    index = tmp_path / "hal_menus" / "koningsdam" / "2025" / "03" / "17" / "index.md"
    content = index.read_text()
    assert "title: 2025-03-17" in content
    assert "hiddenInHomeList: true" in content
    assert f"- [file.pdf](https://cdn/{key})" in content


def test_create_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prefix = "a" * 32
    groups = {
        ("ko", dt.date(2025, 3, 17)): [f"content/ko/menu/abc/{prefix}-file.pdf"],
        ("ko", dt.date(2025, 3, 18)): [f"content/ko/menu/def/{prefix}-file2.pdf"],
        ("na", dt.date(2025, 3, 19)): [f"content/na/menu/ghi/{prefix}-file3.pdf"],
    }

    monkeypatch.setattr(s3_hugo, "group_objects", lambda _bucket, _prefix: groups)

    s3_hugo.create_tree("my-bucket", "content/", tmp_path, "https://cdn")

    root = tmp_path / "hal_menus"
    root_index = root / "_index.md"
    assert root_index.exists()
    assert "hiddenInHomeList: true" in root_index.read_text()
    ship_dir = root / "koningsdam"
    ship_index = ship_dir / "_index.md"
    assert ship_index.exists()
    assert "hiddenInHomeList: true" in ship_index.read_text()
    year_dir = ship_dir / "2025"
    year_index = year_dir / "_index.md"
    assert year_index.exists()
    assert "hiddenInHomeList: true" in year_index.read_text()
    month_dir = year_dir / "03"
    month_index = month_dir / "_index.md"
    assert month_index.exists()
    assert "hiddenInHomeList: true" in month_index.read_text()
    day_index = month_dir / "17" / "index.md"
    assert day_index.exists()
    assert "hiddenInHomeList: true" in day_index.read_text()
    assert "file.pdf" in day_index.read_text()
