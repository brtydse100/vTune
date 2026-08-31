"""Validation helpers for stored report data."""

from __future__ import annotations

from typing import Mapping


def execution(value: object, trial_id: str) -> Mapping[str, object]:
    """Validate an optional resolved trial execution assignment."""
    if value is None:
        return {}
    require(isinstance(value, Mapping), f"trial {trial_id} has invalid execution")
    mode = value.get("mode")
    require(isinstance(mode, str) and mode, f"trial {trial_id} has invalid execution mode")
    result: dict[str, object] = {"mode": mode}
    if "worker" in value:
        require(isinstance(value["worker"], str), f"trial {trial_id} has invalid execution worker")
        result["worker"] = value["worker"]
    if "devices" in value:
        devices = value["devices"]
        require(isinstance(devices, list) and all(isinstance(item, int) and not isinstance(item, bool) and item >= 0 for item in devices), f"trial {trial_id} has invalid execution devices")
        result["devices"] = devices
    if "port" in value:
        port = value["port"]
        require(isinstance(port, int) and not isinstance(port, bool) and 1 <= port <= 65535, f"trial {trial_id} has invalid execution port")
        result["port"] = port
    return result


def require(condition: object, message: str) -> None:
    if not condition:
        raise ValueError(message)
