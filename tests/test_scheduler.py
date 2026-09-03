import asyncio

import pytest

from vllm_optimizer.config.models import ExperimentConfig, VTuneConfig
from vllm_optimizer.execution.scheduler import parallel_trials, sequential_trials
from vllm_optimizer.execution.slots import WorkerSlot, worker_slots
from vllm_optimizer.search.fixed_session import FixedSearchSession
from vllm_optimizer.search.grid import TrialParameters


def test_sequential_and_parallel_scheduling_are_complete_and_duplicate_free() -> None:
    trials = tuple(TrialParameters(f"trial-{i}", {"tensor-parallel-size": i}, {}) for i in (1, 2))
    started = []

    async def execute(parameters, slot):
        await asyncio.sleep(0)
        return parameters.trial_id

    async def run_sequential():
        return [
            item
            async for item in sequential_trials(
                FixedSearchSession(trials),
                execute,
                lambda position, parameters, slot: started.append((position, parameters.trial_id, slot)),
            )
        ]

    sequential = asyncio.run(run_sequential())
    assert [item.value for item in sequential] == ["trial-1", "trial-2"]

    slots = (WorkerSlot("one", (0,), 8100), WorkerSlot("two", (1, 2), 8101))

    async def run_parallel():
        return [
            item async for item in parallel_trials(FixedSearchSession(trials), slots, {}, execute, lambda *args: None)
        ]

    parallel = asyncio.run(run_parallel())
    assert {item.value for item in parallel} == {"trial-1", "trial-2"}
    assert {item.slot.name for item in parallel if item.slot} == {"one", "two"}


def test_parallel_scheduler_rejects_an_unrunnable_trial() -> None:
    trial = TrialParameters("large", {"tensor-parallel-size": 2}, {})

    async def execute(parameters, slot):
        return None

    async def run():
        return [
            item
            async for item in parallel_trials(
                FixedSearchSession((trial,)), (WorkerSlot("small", (0,), 8000),), {}, execute, lambda *args: None
            )
        ]

    with pytest.raises(ValueError, match="no parallel worker"):
        asyncio.run(run())


def test_explicit_worker_slot_validation() -> None:
    config = VTuneConfig(
        1,
        ExperimentConfig("parallel"),
        {"model": "demo"},
        execution={
            "mode": "local_parallel",
            "max_parallel_trials": 2,
            "ports": {"min": 8100, "max": 8101},
            "gpu_allocation": {
                "strategy": "explicit",
                "allow_sharing": False,
                "workers": [{"name": "a", "devices": [0]}, {"name": "b", "devices": [1, 2]}],
            },
        },
    )

    slots = worker_slots(config)
    assert slots == (WorkerSlot("a", (0,), 8100), WorkerSlot("b", (1, 2), 8101))
    assert slots[0].supports({}, {})
    assert not slots[0].supports({"tensor-parallel-size": 2}, {})


@pytest.mark.parametrize(
    "execution, message",
    [
        ({"mode": "invalid"}, "execution.mode"),
        ({"mode": "local_parallel", "max_parallel_trials": 1, "ports": {}, "gpu_allocation": {}}, "workers"),
    ],
)
def test_invalid_parallel_configurations(execution: dict[str, object], message: str) -> None:
    config = VTuneConfig(1, ExperimentConfig("bad"), {"model": "demo"}, execution=execution)
    with pytest.raises(ValueError, match=message):
        worker_slots(config)
