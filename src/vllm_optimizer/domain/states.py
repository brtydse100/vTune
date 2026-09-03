"""Lifecycle states used by the vLLM Optimizer domain model."""

from enum import StrEnum


class RunStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_FAILURES = "completed_with_failures"
    INTERRUPTED = "interrupted"
    FAILED = "failed"


class TrialStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class AttemptStatus(StrEnum):
    CREATED = "created"
    STARTING_SERVER = "starting_server"
    WARMING_UP = "warming_up"
    BENCHMARKING = "benchmarking"
    STOPPING_SERVER = "stopping_server"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
