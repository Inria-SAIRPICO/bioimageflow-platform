"""Logging configuration helpers for application launchers."""

from __future__ import annotations

from importlib.resources import files


def default_log_config_path() -> str:
    return str(files("bioimageflow_server").joinpath("logging.yaml"))


def resolve_log_config_path(log_config: str | None) -> str:
    return log_config or default_log_config_path()
