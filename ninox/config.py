from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel


class OpenAITokens(BaseModel):
    """Holds OpenAI tokens from config."""

    open: str
    closed: str


class TokensConfig(BaseModel):
    """Wrapper for token groups."""

    openai: OpenAITokens


class Config(BaseModel):
    """Root configuration model."""

    tokens: TokensConfig


def load_config(config_path: Path | str) -> Config:
    """Load and parse a TOML config file with pydantic."""
    path = Path(config_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Config(**data)
