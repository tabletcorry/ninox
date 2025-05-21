# ruff: noqa: S101
import click
import pytest
from click.testing import CliRunner

from ninox import main


def test_cli_loads_config(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_load_config(path: str) -> dict[str, str]:
        captured["path"] = path
        return {"token": "x"}

    monkeypatch.setattr(main, "load_config", fake_load_config)

    @click.command()
    @click.pass_obj
    def dummy(obj: object) -> None:
        captured["obj"] = obj

    main.cli.add_command(dummy)
    try:
        runner = CliRunner()
        result = runner.invoke(main.cli, ["dummy"])
        assert result.exit_code == 0
    finally:
        main.cli.commands.pop("dummy", None)

    assert captured["path"] == "~/.config/ninox/config.toml"
    assert captured["obj"] == {"token": "x"}
