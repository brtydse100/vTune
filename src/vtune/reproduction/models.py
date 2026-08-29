"""Structured records captured while executing a trial."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class CommandRecord:
    kind: str
    argv: tuple[str, ...]
    attempt: int
    environment: Mapping[str, str] = field(default_factory=dict)
    benchmark: str | None = None
    repeat: int | None = None

    def to_dict(self) -> dict[str, object]:
        document: dict[str, object] = {
            "kind": self.kind, "attempt": self.attempt,
            "argv": list(self.argv), "environment": dict(self.environment),
        }
        if self.benchmark is not None:
            document["benchmark"] = self.benchmark
        if self.repeat is not None:
            document["repeat"] = self.repeat
        return document


@dataclass(frozen=True, slots=True)
class StartupRecord:
    attempt: int
    seconds: float

    def to_dict(self) -> dict[str, object]:
        return {"attempt": self.attempt, "seconds": round(self.seconds, 6)}
