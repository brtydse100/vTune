"""Checksums and validation for persisted run artifacts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path


def describe_artifacts(values: Mapping[str, object]) -> dict[str, dict[str, object]]:
    records = {}
    for name, value in sorted(values.items()):
        if name == "manifest":
            continue
        path = Path(str(value)).resolve()
        record: dict[str, object] = {"path": str(path), "exists": path.is_file()}
        if path.is_file():
            record.update({"bytes": path.stat().st_size, "sha256": _sha256(path)})
        records[name] = record
    return records


def load_retry_source(
    source: Path, trial_ids: list[str]
) -> tuple[dict[str, object], list[dict[str, object]], tuple[str, ...]]:
    result = _read_json(source / "result.json", "source result.json")
    _schema(result, "source result.json")
    indexed = _indexed_trials(result)
    manifests = []
    warnings = []
    if result.get("status") == "running":
        warnings.append("source result.json still says 'running'; the process may have ended abruptly")
    for trial_id in trial_ids:
        if trial_id not in indexed:
            raise ValueError(f"trial '{trial_id}' is not listed in source result.json")
        trial_dir = source / "trials" / trial_id
        if not trial_dir.is_dir():
            raise ValueError(f"source trial directory was deleted or is missing: {trial_dir}")
        manifest_path = trial_dir / "manifest.json"
        manifest = _read_json(manifest_path, f"manifest for trial '{trial_id}'")
        _schema(manifest, f"manifest for trial '{trial_id}'")
        if manifest.get("trial_id") != trial_id:
            raise ValueError(f"source manifest identity does not match trial '{trial_id}'")
        manifests.append(manifest)
        warnings.extend(artifact_warnings(manifest, trial_id))
    return result, manifests, tuple(warnings)


def _read_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"{label} was deleted or is missing: {path}") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is unreadable or malformed at '{path}': {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def _schema(document: Mapping[str, object], label: str) -> None:
    if document.get("schema_version") != 1:
        raise ValueError(f"{label} has an unsupported or missing schema_version")


def _indexed_trials(result: Mapping[str, object]) -> set[str]:
    values = result.get("trials")
    if not isinstance(values, list):
        raise ValueError("source result.json has an invalid trials list")
    indexed = set()
    for value in values:
        if not isinstance(value, dict) or not isinstance(value.get("trial_id"), str):
            raise ValueError("source result.json has an invalid trial entry")
        indexed.add(value["trial_id"])
    return indexed


def artifact_warnings(manifest: Mapping[str, object], trial_id: str) -> list[str]:
    values = manifest.get("artifacts", {})
    if not isinstance(values, dict):
        raise ValueError(f"manifest for trial '{trial_id}' has invalid artifact records")
    warnings = []
    for name, value in values.items():
        if not isinstance(value, dict) or not isinstance(value.get("path"), str):
            raise ValueError(f"manifest for trial '{trial_id}' has invalid artifact '{name}'")
        path = Path(value["path"])
        if not path.is_file():
            warnings.append(f"trial '{trial_id}' artifact '{name}' is missing: {path}")
        elif isinstance(value.get("sha256"), str) and _sha256(path) != value["sha256"]:
            warnings.append(f"trial '{trial_id}' artifact '{name}' checksum does not match")
    return warnings


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
