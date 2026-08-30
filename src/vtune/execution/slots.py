"""Validated explicit GPU and port assignments for local execution."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from vtune.config.models import VTuneConfig

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True, slots=True)
class WorkerSlot:
    name: str
    devices: tuple[int, ...]
    port: int

    def supports(self, server_args: Mapping[str, object], fixed: Mapping[str, object]) -> bool:
        value = server_args.get(
            "tensor-parallel-size", server_args.get(
                "tensor_parallel_size", fixed.get(
                    "tensor-parallel-size", fixed.get("tensor_parallel_size", 1),
                ),
            ),
        )
        return isinstance(value, int) and not isinstance(value, bool) and value <= len(self.devices)


def execution_mode(config: VTuneConfig) -> str:
    mode = config.execution.get("mode", "sequential")
    if mode not in {"sequential", "local_parallel"}:
        raise ValueError("execution.mode must be sequential or local_parallel")
    return str(mode)


def worker_slots(config: VTuneConfig) -> tuple[WorkerSlot, ...]:
    if execution_mode(config) == "sequential":
        return ()
    _reject_conflicting_gpu_configuration(config)
    maximum = _positive_int(config.execution.get("max_parallel_trials"),
                            "execution.max_parallel_trials")
    allocation = _mapping(config.execution.get("gpu_allocation"),
                          "execution.gpu_allocation")
    unknown = set(allocation) - {"strategy", "allow_sharing", "workers"}
    if unknown:
        raise ValueError(f"unknown gpu_allocation setting(s): {', '.join(sorted(unknown))}")
    if allocation.get("strategy", "explicit") != "explicit":
        raise ValueError("only explicit GPU allocation is currently supported")
    if allocation.get("allow_sharing", False) is not False:
        raise ValueError("parallel GPU sharing is not currently supported")
    definitions = allocation.get("workers")
    if not isinstance(definitions, list) or not definitions:
        raise ValueError("execution.gpu_allocation.workers must be a non-empty list")
    start, stop = _port_range(config.execution.get("ports"))
    if len(definitions) > stop - start + 1:
        raise ValueError("execution.ports does not contain enough unique ports")
    slots = tuple(_slot(value, start + index) for index, value in enumerate(definitions))
    if maximum != len(slots):
        raise ValueError("max_parallel_trials must equal the number of explicit GPU workers")
    _reject_duplicates(slots)
    return slots


def _slot(value: object, port: int) -> WorkerSlot:
    raw = _mapping(value, "GPU worker")
    if set(raw) != {"name", "devices"}:
        raise ValueError("each GPU worker requires only name and devices")
    name, devices = raw["name"], raw["devices"]
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        raise ValueError("GPU worker names must use letters, numbers, '_' or '-'")
    if (not isinstance(devices, list) or not devices or
            any(isinstance(item, bool) or not isinstance(item, int) or item < 0
                for item in devices) or len(set(devices)) != len(devices)):
        raise ValueError("GPU worker devices must be unique non-negative integers")
    return WorkerSlot(name, tuple(devices), port)


def _port_range(value: object) -> tuple[int, int]:
    raw = _mapping(value, "execution.ports")
    if set(raw) != {"min", "max"}:
        raise ValueError("execution.ports requires only min and max")
    start = _positive_int(raw["min"], "execution.ports.min")
    stop = _positive_int(raw["max"], "execution.ports.max")
    if start > stop or stop > 65535:
        raise ValueError("execution.ports must be an ascending valid port range")
    return start, stop


def _reject_duplicates(slots: tuple[WorkerSlot, ...]) -> None:
    if len({slot.name for slot in slots}) != len(slots):
        raise ValueError("parallel worker names must be unique")
    claimed: set[int] = set()
    for slot in slots:
        overlap = claimed.intersection(slot.devices)
        if overlap:
            raise ValueError(f"GPU devices cannot overlap between workers: {sorted(overlap)}")
        claimed.update(slot.devices)


def _reject_conflicting_gpu_configuration(config: VTuneConfig) -> None:
    if "CUDA_VISIBLE_DEVICES" in config.env or "CUDA_VISIBLE_DEVICES" in config.tune_env:
        raise ValueError("local_parallel assigns CUDA_VISIBLE_DEVICES; remove it from env/tune_env")
    if "port" in config.server or "port" in config.tune:
        raise ValueError("local_parallel assigns ports; remove port from server/tune")


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value
