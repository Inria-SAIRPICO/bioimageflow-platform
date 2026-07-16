from __future__ import annotations

import logging
from pathlib import Path
import subprocess
import sys

from bioimageflow_server.logging_config import default_log_config_path, resolve_log_config_path


def test_default_log_config_path_points_to_packaged_yaml() -> None:
    path = Path(default_log_config_path())

    assert path.name == "logging.yaml"
    assert path.is_file()
    assert "bioimageflow_server" in path.read_text(encoding="utf-8")


def test_resolve_log_config_path_accepts_override() -> None:
    assert resolve_log_config_path("/tmp/logging.yaml") == "/tmp/logging.yaml"


def test_packaged_access_formatter_handles_uvicorn_positional_access_records() -> None:
    script = """
import logging
import logging.config
from pathlib import Path

import yaml

from bioimageflow_server.logging_config import default_log_config_path

with Path(default_log_config_path()).open(encoding="utf-8") as handle:
    config = yaml.safe_load(handle)
logging.config.dictConfig(config)
logger = logging.getLogger("uvicorn.access")
handler = logger.handlers[0]
record = logger.makeRecord(
    "uvicorn.access",
    logging.INFO,
    "<logging-config-test>",
    1,
    '%s - "%s %s HTTP/%s" %d',
    ("127.0.0.1:64848", "GET", "/api/v1/tools", "1.1", 200),
    None,
)
print(handler.format(record))
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == (
        'INFO:uvicorn.access:127.0.0.1:64848 - "GET /api/v1/tools HTTP/1.1" 200'
    )


def test_packaged_formatter_integration_does_not_contaminate_caplog(caplog) -> None:
    logger = logging.getLogger("bioimageflow_server.ws")

    with caplog.at_level(logging.DEBUG, logger=logger.name):
        logger.debug("logging order sentinel")

    assert "logging order sentinel" in caplog.text
    assert logging.getLogger("bioimageflow").propagate is True
