# ruff: noqa: S101
from pathlib import Path

import pytest

from ninox.config import load_config


def test_load_config(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text("""[tokens.openai]
open = 'foo'
closed = 'bar'
""")
    data = load_config(cfg)
    assert data.tokens.openai.open == "foo"
    assert data.tokens.openai.closed == "bar"


def test_load_config_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.toml")
