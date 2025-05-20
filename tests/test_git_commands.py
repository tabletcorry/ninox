# ruff: noqa: S101
from pathlib import Path

import click
import pytest
from dulwich import porcelain
from dulwich.repo import Repo

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
    monkeypatch.setattr(git_commands, "load_config", lambda _path: make_config())
    monkeypatch.setattr(click, "confirm", lambda *_a, **_k: False)
    monkeypatch.setattr(click, "edit", lambda msg: msg)

    callback = git_commands.commit.callback
    assert callback is not None
    callback("model")

    repo = Repo(str(tmp_path))
    last = repo[repo.head()]
    assert last.message.decode().strip() == "Update file"
