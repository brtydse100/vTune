"""Sequential session over the deterministic grid."""

from __future__ import annotations

from vtune.config.models import VTuneConfig
from vtune.search.grid import TrialParameters, expand_grid


class GridSearchSession:
    def __init__(self, config: VTuneConfig) -> None:
        self._trials = expand_grid(config)
        self._position = 0

    @property
    def total(self) -> int:
        return len(self._trials)

    def suggest(self) -> TrialParameters | None:
        if self._position >= self.total:
            return None
        trial = self._trials[self._position]
        self._position += 1
        return trial

    def complete(self, trial: TrialParameters, value: float) -> None:
        pass

    def fail(self, trial: TrialParameters, interrupted: bool = False) -> None:
        pass
