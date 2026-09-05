"""Shell-free, bounded subprocess execution for a workspace."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .workspace import Workspace


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    cwd: str
    returncode: int | None
    output: str
    timed_out: bool
    output_truncated: bool
    error: str | None = None


class CommandRunner:
    def __init__(self, workspace: Workspace, *, default_timeout_seconds: float = 30, max_output_bytes: int = 64 * 1024) -> None:
        if default_timeout_seconds <= 0 or max_output_bytes < 1:
            raise ValueError("Command limits must be positive")
        self.workspace = workspace
        self.default_timeout_seconds = default_timeout_seconds
        self.max_output_bytes = max_output_bytes

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path = ".",
        timeout_seconds: float | None = None,
        input_text: str | None = None,
    ) -> CommandResult:
        if not command or any(not isinstance(argument, str) or not argument for argument in command):
            raise ValueError("Command must be a non-empty sequence of non-empty strings")
        directory = self.workspace.resolve(cwd)
        if not directory.is_dir():
            raise ValueError(f"Command working directory is not a directory: {cwd}")
        timeout = self.default_timeout_seconds if timeout_seconds is None else timeout_seconds
        if timeout <= 0:
            raise ValueError("Command timeout must be positive")
        try:
            process = subprocess.Popen(
                list(command),
                cwd=directory,
                stdin=subprocess.PIPE if input_text is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
                start_new_session=True,
            )
        except OSError as error:
            return CommandResult(tuple(command), self.workspace.relative(directory), None, "", False, False, str(error))

        output = bytearray()
        truncated = False

        def collect() -> None:
            nonlocal truncated
            assert process.stdout is not None
            while chunk := process.stdout.read(8_192):
                remaining = self.max_output_bytes - len(output)
                if remaining > 0:
                    output.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    truncated = True

        reader = threading.Thread(target=collect, daemon=True)
        reader.start()
        if input_text is not None:
            assert process.stdin is not None
            process.stdin.write(input_text.encode("utf-8"))
            process.stdin.close()
        timed_out = False
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._terminate(process)
        reader.join()
        return CommandResult(
            tuple(command),
            self.workspace.relative(directory),
            process.returncode,
            output.decode("utf-8", errors="replace"),
            timed_out,
            truncated,
        )

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
