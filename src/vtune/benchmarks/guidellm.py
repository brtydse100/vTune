"""GuideLLM configuration, command construction, and result normalization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from pathlib import Path
import re

from vtune.config.models import VTuneConfig
from vtune.domain.benchmark import BenchmarkResult, WorkloadResult
from vtune.benchmarks.timing import normalize_durations

_RUN_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


@dataclass(frozen=True, slots=True)
class GuideLLMPlan:
    run_name: str
    argv: tuple[str, ...]
    directory: Path
    json_path: Path
    log_path: Path


def configured_runs(config: VTuneConfig) -> tuple[Mapping[str, object], ...]:
    unknown = set(config.benchmark) - {"runs", "repeats"}
    if unknown:
        raise ValueError(f"Unsupported benchmark setting(s): {', '.join(sorted(unknown))}")
    runs = config.benchmark.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("'benchmark.runs' must be a non-empty list")
    validated: list[Mapping[str, object]] = []
    names: set[str] = set()
    for index, value in enumerate(runs):
        run = _mapping(value, f"run {index}")
        unknown_run = set(run) - {
            "name", "request_format", "profile", "constraints", "data"
        }
        if unknown_run:
            options = ", ".join(sorted(unknown_run))
            raise ValueError(f"Unsupported setting(s) in benchmark run {index}: {options}")
        name = run.get("name")
        if not isinstance(name, str) or not _RUN_NAME.fullmatch(name):
            raise ValueError("benchmark run names must use letters, numbers, '_' or '-'")
        if name in names:
            raise ValueError(f"duplicate benchmark run name: {name}")
        names.add(name)
        data = run.get("data")
        if not isinstance(data, list) or len(data) != 1:
            raise ValueError(f"benchmark run '{name}' must configure exactly one dataset")
        validated.append(run)
    return tuple(validated)


def configured_repeats(config: VTuneConfig) -> int:
    value = config.benchmark.get("repeats", 1)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("benchmark.repeats must be a positive integer")
    return value


def build_plan(
    config: VTuneConfig, run: Mapping[str, object], endpoint: str, artifacts: Path,
) -> GuideLLMPlan:
    name = run["name"]
    request_format = run.get("request_format", "/v1/completions")
    if not isinstance(request_format, str) or not request_format.strip():
        raise ValueError("benchmark request_format must be a non-empty string")
    directory = Path(artifacts) / str(name)
    json_path = directory / "results.json"
    argv = [
        "guidellm", "run", "--backend",
        _serialize({"kind": "openai_http", "target": endpoint,
                    "model": config.model.path, "request_format": request_format}),
        "--profile", _serialize(_mapping(run.get("profile"), "profile")),
    ]
    for option, label in (("constraints", "constraint"), ("data", "data")):
        values = run.get(option, [])
        if not isinstance(values, list):
            raise ValueError(f"benchmark run '{option}' must be a list")
        for value in values:
            if label == "constraint" and isinstance(value, dict) and value.get("kind") == "max_duration":
                value = {**value, "seconds": normalize_durations(value.get("seconds"))}
            argv.extend((f"--{label}", _serialize(_mapping(value, label))))
    argv.extend(("--output", f"kind=json,path={json_path}",
                 "--disable-console-interactive"))
    return GuideLLMPlan(str(name), tuple(argv), directory, json_path,
                        directory / "benchmark.log")


def parse_result(path: Path, run_name: str) -> BenchmarkResult:
    source = Path(path)
    try:
        root = _mapping(json.loads(source.read_text(encoding="utf-8")), "result")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read GuideLLM JSON result: {error}") from error
    metadata = _mapping(root.get("metadata"), "metadata")
    version = metadata.get("guidellm_version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("GuideLLM result is missing its version")
    benchmarks = root.get("benchmarks")
    if not isinstance(benchmarks, list) or not benchmarks:
        raise ValueError("GuideLLM result must contain benchmarks")
    workloads = tuple(
        WorkloadResult(index, _mapping(item.get("config"), f"benchmark {index} config"),
                       _mapping(item.get("metrics"), f"benchmark {index} metrics"))
        for index, value in enumerate(benchmarks)
        for item in (_mapping(value, f"benchmark {index}"),)
    )
    return BenchmarkResult(run_name, "guidellm", version, workloads, source)


def _serialize(values: Mapping[str, object]) -> str:
    kind = values.get("kind")
    if not isinstance(kind, str) or not kind.strip():
        raise ValueError("GuideLLM options require a non-empty 'kind'")
    return ",".join(pair for key, value in values.items() for pair in _pairs(key, value))


def _pairs(path: str, value: object) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        return tuple(pair for key, item in value.items()
                     for pair in _pairs(f"{path}.{key}", item))
    if isinstance(value, list | tuple):
        return tuple(pair for index, item in enumerate(value)
                     for pair in _pairs(f"{path}[{index}]", item))
    if isinstance(value, bool):
        rendered = str(value).lower()
    if isinstance(value, str | int | float) and not isinstance(value, bool):
        rendered = str(value)
    elif value is None:
        rendered = "null"
    elif not isinstance(value, bool):
        raise ValueError(f"Unsupported GuideLLM value at '{path}'")
    if "," in rendered:
        raise ValueError(f"GuideLLM string values cannot contain commas: '{path}'")
    return (f"{path}={rendered}",)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"GuideLLM {label} must be an object")
    return value
