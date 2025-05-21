# ruff: noqa: S101
import io
from pathlib import Path
from typing import TYPE_CHECKING, cast

import click
import pytest
from dulwich import porcelain
from dulwich.repo import Repo

if TYPE_CHECKING:
    from collections.abc import Callable

from ninox import git_commands


class FakeCompletions:
    def __init__(self, message: str) -> None:
        self._message = message

    def create(self, **_kwargs: object) -> object:
        return type(
            "Resp",
            (),
            {
                "choices": [
                    type(
                        "C",
                        (),
                        {"message": type("M", (), {"content": self._message})()},
                    )
                ]
            },
        )()


class FakeChat:
    def __init__(self, message: str) -> None:
        self.completions = FakeCompletions(message)


class FakeClient:
    def __init__(self, *, message: str) -> None:
        self.chat = FakeChat(message)


def make_config() -> object:
    return type(
        "Config",
        (),
        {
            "tokens": type(
                "Tokens", (), {"openai": type("Open", (), {"open": "tok"})()}
            )()
        },
    )()


def test_commit_creates_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = porcelain.init(tmp_path)
    monkeypatch.chdir(tmp_path)
    Path("file.txt").write_text("hello", encoding="utf-8")
    porcelain.add(repo.path, "file.txt")  # type: ignore[no-untyped-call]
    porcelain.commit(repo.path, message=b"init")  # type: ignore[no-untyped-call]

    Path("file.txt").write_text("world", encoding="utf-8")
    porcelain.add(repo.path, "file.txt")  # type: ignore[no-untyped-call]

    monkeypatch.setattr(
        git_commands, "OpenAI", lambda *_, **__: FakeClient(message="Update file")
    )
    monkeypatch.setattr(click, "edit", lambda msg: msg)

    callback = git_commands.commit.callback
    assert callback is not None
    wrapped = cast("Callable[..., None]", getattr(callback, "__wrapped__", None))
    assert wrapped is not None
    wrapped(make_config(), "model", stage_all=False, dry_run=False, paths=())

    repo = Repo(str(tmp_path))
    last = repo[repo.head()]
    assert last.message.decode().strip() == "Update file"


def test_commit_only_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = porcelain.init(tmp_path)
    monkeypatch.chdir(tmp_path)
    Path("a.txt").write_text("hello", encoding="utf-8")
    Path("b.txt").write_text("hello", encoding="utf-8")
    porcelain.add(repo.path, ["a.txt", "b.txt"])  # type: ignore[no-untyped-call]
    porcelain.commit(repo.path, message=b"init")  # type: ignore[no-untyped-call]

    Path("a.txt").write_text("new", encoding="utf-8")
    Path("b.txt").write_text("new", encoding="utf-8")

    monkeypatch.setattr(
        git_commands, "OpenAI", lambda *_, **__: FakeClient(message="Msg")
    )
    monkeypatch.setattr(click, "edit", lambda msg: msg)

    callback = git_commands.commit.callback
    assert callback is not None
    wrapped = cast("Callable[..., None]", getattr(callback, "__wrapped__", None))
    assert wrapped is not None
    wrapped(make_config(), "model", stage_all=False, dry_run=False, paths=("a.txt",))

    repo = Repo(str(tmp_path))
    head = repo.head()
    last = repo[head]
    prev = repo[last.parents[0]]
    diff_io = io.BytesIO()
    porcelain.diff_tree(repo.path, prev.tree, last.tree, outstream=diff_io)
    patch = diff_io.getvalue()
    assert b"a.txt" in patch
    assert b"b.txt" not in patch


def test_commit_all_option(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = porcelain.init(tmp_path)
    monkeypatch.chdir(tmp_path)
    Path("a.txt").write_text("hello", encoding="utf-8")
    porcelain.add(repo.path, "a.txt")  # type: ignore[no-untyped-call]
    porcelain.commit(repo.path, message=b"init")  # type: ignore[no-untyped-call]

    Path("a.txt").write_text("new", encoding="utf-8")

    monkeypatch.setattr(
        git_commands, "OpenAI", lambda *_, **__: FakeClient(message="Msg")
    )
    monkeypatch.setattr(click, "edit", lambda msg: msg)

    callback = git_commands.commit.callback
    assert callback is not None
    wrapped = cast("Callable[..., None]", getattr(callback, "__wrapped__", None))
    assert wrapped is not None
    wrapped(make_config(), "model", stage_all=True, dry_run=False, paths=())

    status = porcelain.status(repo.path)  # type: ignore[no-untyped-call]
    assert status.unstaged == []


def test_commit_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = porcelain.init(tmp_path)
    monkeypatch.chdir(tmp_path)
    Path("file.txt").write_text("hello", encoding="utf-8")
    porcelain.add(repo.path, "file.txt")  # type: ignore[no-untyped-call]
    porcelain.commit(repo.path, message=b"init")  # type: ignore[no-untyped-call]

    Path("file.txt").write_text("new", encoding="utf-8")
    porcelain.add(repo.path, "file.txt")  # type: ignore[no-untyped-call]

    monkeypatch.setattr(
        git_commands, "OpenAI", lambda *_, **__: FakeClient(message="Msg")
    )

    def fail_edit(_msg: str) -> str:
        raise AssertionError("edit should not be called")

    monkeypatch.setattr(click, "edit", fail_edit)

    callback = git_commands.commit.callback
    assert callback is not None
    wrapped = cast("Callable[..., None]", getattr(callback, "__wrapped__", None))
    assert wrapped is not None
    wrapped(make_config(), "model", stage_all=False, dry_run=True, paths=())

    repo = Repo(str(tmp_path))
    assert len(list(repo.get_walker())) == 1
