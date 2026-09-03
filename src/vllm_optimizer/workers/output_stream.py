"""Incremental subprocess output copying."""

from __future__ import annotations

import asyncio
from typing import IO


async def mirror_output(stream: asyncio.StreamReader, log: IO[str], label: str, console: bool) -> None:
    while chunk := await stream.read(4096):
        text = chunk.decode("utf-8", errors="replace")
        log.write(text)
        log.flush()
        if console:
            print(f"[{label}] {text}", end="", flush=True)
