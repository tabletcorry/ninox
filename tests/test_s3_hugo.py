# ruff: noqa: S101
import datetime as dt
from collections.abc import Iterable
from pathlib import Path

import click
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

    section2 = tmp_path / "bar"
    s3_hugo.ensure_section(section2, "Bar", "A ship")
    assert (section2 / "_index.md").read_text() == (
        "---\n"
        "title: Bar\n"
        "ShowReadingTime: false\n"
        "hideMeta: true\n"
        "hideSummary: true\n"
        "hiddenInHomeList: true\n"
        "description: >-\n"
        "  A ship\n"
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
    year_dir = tmp_path / "hal_menus" / "koningsdam" / "2025"
    index = year_dir / "index.md"
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
    assert not (year_dir / "_index.md").exists()


def test_write_year_page_with_description(tmp_path: Path) -> None:
    prefix = "a" * 32
    d = dt.date(2025, 3, 17)
    key = f"content/ko/menu/abc/{prefix}-file.pdf"
    s3_hugo.write_year_page(
        tmp_path, "ko", 2025, {d: [key]}, "https://cdn", description="A ship"
    )
    year_dir = tmp_path / "hal_menus" / "koningsdam" / "2025"
    content = (year_dir / "index.md").read_text()
    assert "description: >-\n  A ship from 2025" in content


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
    assert not (year_dir / "_index.md").exists()
    year_page = year_dir / "index.md"
    assert year_page.exists()
    content = year_page.read_text()
    assert '{{< details title="March" >}}' in content
    assert "file.pdf" in content


def test_create_tree_with_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prefix = "a" * 32
    groups = {("ko", dt.date(2025, 3, 17)): [f"content/ko/menu/abc/{prefix}-file.pdf"]}

    monkeypatch.setattr(s3_hugo, "group_objects", lambda _bucket, _prefix: groups)

    config = tmp_path / "config.toml"
    config.write_text("""[ships]\nko = 'The best'\n""")

    s3_hugo.create_tree("my-bucket", "content/", tmp_path, "https://cdn", config)

    ship_dir = tmp_path / "hal_menus" / "koningsdam"
    ship_content = (ship_dir / "_index.md").read_text()
    assert "description: >-\n  The best" in ship_content
    year_page = ship_dir / "2025" / "index.md"
    assert "description: >-\n  The best from 2025" in year_page.read_text()


def test_generate_menu_tree_autoload_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "ninox_config.toml"
    config.write_text("""[ships]\nko = 'Desc'\n""")
    monkeypatch.chdir(tmp_path)

    captured: dict[str, Path | None] = {}

    def fake_create_tree(
        _bucket: str,
        _prefix: str,
        _output: Path,
        _cdn_host: str,
        config_path: Path | None,
    ) -> None:
        captured["config"] = config_path

    monkeypatch.setattr(s3_hugo, "create_tree", fake_create_tree)
    callback = s3_hugo.generate_menu_tree.callback
    assert callback is not None
    callback("b", "content/", tmp_path, "https://cdn", None)
    assert captured["config"] == config


def test_generate_menu_tree_prompt_abort(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s3_hugo.click, "confirm", lambda *_a, **_k: False)  # type: ignore[attr-defined]
    callback = s3_hugo.generate_menu_tree.callback
    assert callback is not None
    with pytest.raises(click.Abort):
        callback("b", "content/", tmp_path, "https://cdn", None)


def test_generate_menu_tree_prompt_continue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(s3_hugo.click, "confirm", lambda *_a, **_k: True)  # type: ignore[attr-defined]
    captured: dict[str, Path | None] = {}

    def fake_create_tree(
        _bucket: str,
        _prefix: str,
        _output: Path,
        _cdn_host: str,
        config_path: Path | None,
    ) -> None:
        captured["config"] = config_path

    monkeypatch.setattr(s3_hugo, "create_tree", fake_create_tree)
    callback = s3_hugo.generate_menu_tree.callback
    assert callback is not None
    callback("b", "content/", tmp_path, "https://cdn", None)
    assert captured["config"] is None
