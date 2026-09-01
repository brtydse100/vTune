"""vLLM Bench Serve command construction and result normalization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
from urllib.parse import urlsplit

from vtune.config.models import VTuneConfig
from vtune.config.runtime import model_path
from vtune.domain.benchmark import BenchmarkResult, WorkloadResult
from vtune.benchmarks.metrics import normalize_vllm_metrics

_RESERVED = {"backend", "model", "host", "port", "base-url", "save-result", "append-result",
             "result-dir", "result-filename"}


@dataclass(frozen=True, slots=True)
class VLLMBenchPlan:
    run_name: str
    argv: tuple[str, ...]
    directory: Path
    json_path: Path
    log_path: Path


def build_plan(config: VTuneConfig, run: Mapping[str, object], endpoint: str,
               artifacts: Path) -> VLLMBenchPlan:
    name = str(run["name"])
    args = _mapping(run.get("args", {}), f"vllm benchmark run '{name}' args")
    normalized = {key.replace("_", "-"): value for key, value in args.items()}
    if protected := _RESERVED.intersection(normalized):
        raise ValueError(f"vTune controls vLLM benchmark argument(s): {', '.join(sorted(protected))}")
    parsed = urlsplit(endpoint)
    directory = Path(artifacts) / name
    result = directory / "results.json"
    argv = ["vllm", "bench", "serve", "--backend", "vllm",
            "--model", model_path(config),
            "--host", parsed.hostname or "127.0.0.1", "--port", str(parsed.port or 8000)]
    for key, value in normalized.items():
        argv.extend(_argument(key, value))
    argv.extend(("--save-result", "--result-dir", str(directory),
                 "--result-filename", result.name, "--disable-tqdm"))
    return VLLMBenchPlan(name, tuple(argv), directory, result,
                         directory / "benchmark.log")


def parse_result(path: Path, run_name: str) -> BenchmarkResult:
    source = Path(path)
    try:
        document = _mapping(json.loads(source.read_text(encoding="utf-8")), "result")
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read vLLM benchmark JSON result: {error}") from error
    metrics = normalize_vllm_metrics(document)
    if isinstance(document.get("num_prompts"), int) and not isinstance(document.get("num_prompts"), bool):
        metrics["request_total"] = document["num_prompts"]
    configuration = {key: document[key] for key in (
        "backend", "model_id", "num_prompts", "request_rate", "burstiness",
        "max_concurrency", "dataset_name",
    ) if key in document}
    return BenchmarkResult(run_name, "vllm", _version(),
                           (WorkloadResult(0, configuration, metrics),), source)


def _argument(name: str, value: object) -> tuple[str, ...]:
    flag = f"--{name}"
    if isinstance(value, bool):
        return (flag,) if value else ()
    if isinstance(value, list):
        return tuple(item for entry in value for item in (flag, str(entry)))
    if value is None or not isinstance(value, str | int | float):
        raise ValueError(f"Unsupported vLLM benchmark value for '{name}'")
    return flag, str(value)


def _version() -> str:
    try:
        return version("vllm")
    except PackageNotFoundError:
        return "unknown"


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{label} must be an object")
    return value
