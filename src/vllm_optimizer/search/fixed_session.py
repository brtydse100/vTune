"""Search session for explicitly selected retry configurations."""

from vllm_optimizer.search.grid import TrialParameters


class FixedSearchSession:
    def __init__(self, trials: tuple[TrialParameters, ...]) -> None:
        self._trials = trials
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
