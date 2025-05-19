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
    assert (section / "_index.md").read_text() == (
        "---\n"
        "title: Foo\n"
        "ShowReadingTime: false\n"
        "hideMeta: true\n"
        "hideSummary: true\n"
        "hiddenInHomeList: true\n"
        "---\n"
    )
    # second call should not fail or change content
    s3_hugo.ensure_section(section, "Foo")
    assert (section / "_index.md").read_text() == (
        "---\n"
        "title: Foo\n"
        "ShowReadingTime: false\n"
        "hideMeta: true\n"
        "hideSummary: true\n"
        "hiddenInHomeList: true\n"
        "---\n"
    )


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


def test_write_year_page(tmp_path: Path) -> None:
    prefix = "a" * 32
    d1 = dt.date(2025, 3, 17)
    d2 = dt.date(2025, 4, 1)
    key1 = f"content/ko/menu/abc/{prefix}-file.pdf"
    key2 = f"content/ko/menu/def/{prefix}-file2.pdf"
    s3_hugo.write_year_page(
        tmp_path, "ko", 2025, {d1: [key1], d2: [key2]}, "https://cdn"
    )
    index = tmp_path / "hal_menus" / "koningsdam" / "2025" / "index.md"
    content = index.read_text()
    assert "title: 2025" in content
    assert "ShowReadingTime: false" in content
    assert "hideMeta: true" in content
    assert "hideSummary: true" in content
    assert "hiddenInHomeList: true" in content
    assert '{{< details title="March" >}}' in content
    assert '{{< details title="April" >}}' in content
    assert f"- [file.pdf](https://cdn/{key1})" in content
    assert f"- [file2.pdf](https://cdn/{key2})" in content


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
    root_content = root_index.read_text()
    assert "hideMeta: true" in root_content
    assert "hideSummary: true" in root_content
    assert "ShowReadingTime: false" in root_content
    assert "hiddenInHomeList: true" in root_content
    ship_dir = root / "koningsdam"
    ship_index = ship_dir / "_index.md"
    assert ship_index.exists()
    ship_content = ship_index.read_text()
    assert "hideMeta: true" in ship_content
    assert "hideSummary: true" in ship_content
    assert "ShowReadingTime: false" in ship_content
    year_dir = ship_dir / "2025"
    year_index = year_dir / "_index.md"
    assert year_index.exists()
    year_content = year_index.read_text()
    assert "hideMeta: true" in year_content
    assert "hideSummary: true" in year_content
    assert "ShowReadingTime: false" in year_content
    assert "hiddenInHomeList: true" in year_content
    year_page = year_dir / "index.md"
    assert year_page.exists()
    content = year_page.read_text()
    assert '{{< details title="March" >}}' in content
    assert "file.pdf" in content
