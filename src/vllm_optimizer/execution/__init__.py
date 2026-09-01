"""Local execution-slot configuration."""

from .slots import WorkerSlot, execution_mode, worker_slots
from .scheduler import ScheduledResult, parallel_trials, sequential_trials
from .trial_executor import TrialExecutor

__all__ = [
    "ScheduledResult", "TrialExecutor", "WorkerSlot", "execution_mode", "parallel_trials",
    "sequential_trials", "worker_slots",
]
