"""Coordinator-owned scheduling of independent local trial executions."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Generic, TypeVar

from vllm_optimizer.execution.slots import WorkerSlot
from vllm_optimizer.search.grid import TrialParameters
from vllm_optimizer.search.strategy import SearchSession

T = TypeVar("T")
Execute = Callable[[TrialParameters, WorkerSlot | None], Awaitable[T]]
Started = Callable[[int, TrialParameters, WorkerSlot | None], None]


@dataclass(frozen=True, slots=True)
class ScheduledResult(Generic[T]):
    position: int
    parameters: TrialParameters
    slot: WorkerSlot | None
    value: T


async def sequential_trials(
    search: SearchSession, execute: Execute[T], started: Started
) -> AsyncIterator[ScheduledResult[T]]:
    position = 0
    while (parameters := search.suggest()) is not None:
        position += 1
        started(position, parameters, None)
        yield ScheduledResult(position, parameters, None, await execute(parameters, None))


async def parallel_trials(
    search: SearchSession,
    slots: tuple[WorkerSlot, ...],
    fixed: dict[str, object],
    execute: Execute[T],
    started: Started,
) -> AsyncIterator[ScheduledResult[T]]:
    available = list(slots)
    pending: list[tuple[int, TrialParameters]] = []
    active: dict[asyncio.Future[T], tuple[int, TrialParameters, WorkerSlot]] = {}
    exhausted, position = False, 0
    try:
        while active or pending or not exhausted:
            made_progress = True
            while available and made_progress:
                made_progress = _start_compatible(pending, available, active, fixed, execute, started)
                if made_progress:
                    continue
                parameters = search.suggest()
                if parameters is None:
                    exhausted = True
                    break
                position += 1
                pending.append((position, parameters))
                made_progress = True
            if not active:
                if pending:
                    raise ValueError("no parallel worker can run a pending trial")
                break
            done, _ = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                trial_position, parameters, slot = active.pop(task)
                available.append(slot)
                yield ScheduledResult(trial_position, parameters, slot, task.result())
    finally:
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)


def _start_compatible(
    pending: list[tuple[int, TrialParameters]],
    available: list[WorkerSlot],
    active: dict[asyncio.Future[T], tuple[int, TrialParameters, WorkerSlot]],
    fixed: dict[str, object],
    execute: Execute[T],
    started: Started,
) -> bool:
    for pending_index, (position, parameters) in enumerate(pending):
        for slot_index, slot in enumerate(available):
            if not slot.supports(parameters.server_args, fixed):
                continue
            pending.pop(pending_index)
            available.pop(slot_index)
            started(position, parameters, slot)
            task = asyncio.ensure_future(execute(parameters, slot))
            active[task] = (position, parameters, slot)
            return True
    return False
