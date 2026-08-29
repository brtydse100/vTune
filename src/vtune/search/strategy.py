"""Common search-session boundary used by the orchestrator."""

from __future__ import annotations

from typing import Protocol

from vtune.search.grid import TrialParameters


class SearchSession(Protocol):
    @property
    def total(self) -> int: ...

    def suggest(self) -> TrialParameters | None: ...

    def complete(self, trial: TrialParameters, value: float) -> None: ...

    def fail(self, trial: TrialParameters, interrupted: bool = False) -> None: ...
