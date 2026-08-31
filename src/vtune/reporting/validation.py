"""Validation helpers for stored report data."""

from __future__ import annotations

from typing import Mapping


def execution(value: object, trial_id: str) -> Mapping[str, object]:
    """Validate an optional resolved trial execution assignment."""
    if value is None:
        return {}
    require(isinstance(value, Mapping), f"trial {trial_id} has invalid execution")
    require(set(value) <= {"mode", "worker", "devices", "port"},
            f"trial {trial_id} has unknown execution fields")
    mode = value.get("mode")
    require(mode in {"sequential", "local_parallel"},
            f"trial {trial_id} has invalid execution mode")
    result: dict[str, object] = {"mode": mode}
    if mode == "sequential":
        require(set(value) == {"mode"}, f"trial {trial_id} has invalid sequential execution")
        return result
    worker, devices, port = value.get("worker"), value.get("devices"), value.get("port")
    require(isinstance(worker, str) and worker.strip(), f"trial {trial_id} has invalid execution worker")
    require(isinstance(devices, list) and devices, f"trial {trial_id} has invalid execution devices")
    if isinstance(devices, list):
        devices = value["devices"]
        require(all(isinstance(item, int) and not isinstance(item, bool) and item >= 0 for item in devices) and len(set(devices)) == len(devices), f"trial {trial_id} has invalid execution devices")
    require(isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535, f"trial {trial_id} has invalid execution port")
    result.update({"worker": worker, "devices": devices, "port": port})
    return result


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)


def object_list(document: Mapping[str, object], name: str) -> list[Mapping[str, object]]:
    value = document.get(name)
    require(isinstance(value, list) and all(isinstance(item, Mapping) for item in value),
            f"run result has invalid {name}")
    return value


def mapping(document: Mapping[str, object], name: str) -> Mapping[str, object]:
    value = document.get(name, {})
    require(isinstance(value, Mapping), f"stored {name} must be an object")
    return value


def text(document: Mapping[str, object], name: str) -> str:
    value = document.get(name)
    require(isinstance(value, str) and bool(value), f"stored {name} must be text")
    return value


def optional_text(value: object) -> str | None:
    return value if isinstance(value, str) else None
