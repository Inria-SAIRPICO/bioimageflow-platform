"""Real Wetlands worker controlled by an explicit socket handshake."""

import json
import os
import socket
from pathlib import Path
from typing import Annotated, Any

from bioimageflow_core import (
    Arguments,
    Connectable,
    EnvironmentSpec,
    GUIMeta,
    IOModel,
    ProcessingTool,
    RowConsumption,
    Template,
)


class HeldWorkerNumbers(ProcessingTool):
    """Announce worker identity, wait for release, then publish exact output."""

    display_name = "Held Worker Numbers"
    row_consumption = RowConsumption.MAPPED
    environment = EnvironmentSpec(
        name="platform-worker-numbers",
        dependencies={"python": "3.12"},
    )

    class Inputs(IOModel):
        value: int
        control_port: int
        multiplier: Annotated[
            int,
            GUIMeta(
                display_name="Multiplier",
                description="Set to zero to exercise the deterministic worker failure path.",
                connectable=Connectable.NEVER,
            ),
        ] = 4

    class Outputs(IOModel):
        multiplied: int
        process_id: int
        report: Path = Template("held_number_{value}.txt")

    def process_row(self, arguments: Arguments, *, task: Any = None) -> Outputs | list:
        with socket.create_connection(("127.0.0.1", arguments.control_port)) as control:
            control.sendall(
                (
                    json.dumps(
                        {
                            "event": "started",
                            "process_id": os.getpid(),
                            "value": arguments.value,
                            "multiplier": arguments.multiplier,
                        }
                    )
                    + "\n"
                ).encode()
            )
            control.settimeout(0.1)
            while True:
                try:
                    command = control.recv(1)
                except TimeoutError:
                    if task is None or not task.cancel_requested:
                        continue
                    control.sendall(
                        (json.dumps({"event": "cancellation_observed"}) + "\n").encode()
                    )
                    task.cancel()
                    control.sendall(
                        (json.dumps({"event": "cancellation_acknowledged"}) + "\n").encode()
                    )
                    return []
                if command != b"1":
                    raise RuntimeError("Held worker control connection closed before release")
                break

        if arguments.multiplier == 0:
            raise RuntimeError(
                "Controlled worker failure: multiplier must not be zero"
            )

        multiplied = arguments.value * arguments.multiplier
        report = Path(arguments.report)
        report.write_text(
            f"{arguments.value} * {arguments.multiplier} = {multiplied}\n"
        )
        return self.Outputs(
            multiplied=multiplied,
            process_id=os.getpid(),
            report=report,
        )
