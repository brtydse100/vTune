"""Small dependency-free charts for the static dashboard."""

from __future__ import annotations

from html import escape

from vllm_optimizer.domain.trial_report import TrialReport
from vllm_optimizer.managers.scoring import TrialScore
from vllm_optimizer.reporting.analysis import parameter_effects, trial_metric


def history_chart(trials: tuple[TrialReport, ...], ranking: tuple[TrialScore, ...]) -> str:
    scores = {item.trial_id: item.value for item in ranking}
    points = [(report.trial_id, scores[report.trial_id]) for report in trials if report.trial_id in scores]
    if not points:
        return _empty("No completed tuned trials.")
    high, low = max(value for _, value in points), min(value for _, value in points)
    span = high - low or 1
    step = 520 / max(len(points) - 1, 1)
    coords = [(40 + index * step, 280 - (value - low) / span * 230) for index, (_, value) in enumerate(points)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in coords)
    dots = "".join(
        f"<circle cx='{x:.1f}' cy='{y:.1f}' r='5'><title>{escape(name)}: {value:.4f}</title></circle>"
        for (name, value), (x, y) in zip(points, coords, strict=True)
    )
    return _svg(
        f"<polyline points='{line}' fill='none' stroke='#2563eb' stroke-width='3'/>{dots}",
        "Trial score history",
        "Trial order",
        "Score",
    )


def comparison_chart(ranking: tuple[TrialScore, ...], baseline: TrialScore | None) -> str:
    values = ([("Baseline", baseline.value)] if baseline else []) + [
        (item.trial_id, item.value) for item in ranking[:5]
    ]
    if not values:
        return _empty("No scores available.")
    bars = "".join(
        f"<div class='hbar'><span>{escape(name)}</span><i style='width:{_width(value, values):.1f}%'></i>"
        f"<b>{value:.4f}</b></div>"
        for name, value in values
    )
    return f"<div class='bars'>{bars}</div>"


def effect_charts(ranking: tuple[TrialScore, ...]) -> str:
    effects = parameter_effects(ranking)
    if not effects:
        return _empty("No parameter had multiple evaluated values.")
    sections = []
    for name, groups in effects.items():
        values = [(value, score) for value, score, _ in groups]
        bars = "".join(
            f"<div class='hbar'><span>{escape(value)}</span>"
            f"<i style='width:{_width(score, values):.1f}%'></i>"
            f"<b>{score:.4f} <small>n={count}</small></b></div>"
            for value, score, count in groups
        )
        sections.append(f"<h3><code>{escape(name)}</code></h3>{bars}")
    return "".join(sections)


def scatter_chart(trials: tuple[TrialReport, ...]) -> str:
    points = [
        (report.trial_id, throughput, latency)
        for report in trials
        if (throughput := trial_metric(report, "output_tokens_per_second")) is not None
        and (latency := trial_metric(report, "time_to_first_token_ms")) is not None
    ]
    if not points:
        return _empty("Throughput and TTFT were not both available.")
    max_x = max(point[1] for point in points) or 1
    max_y = max(point[2] for point in points) or 1
    dots = "".join(
        f"<circle cx='{40 + x / max_x * 520:.1f}' cy='{280 - y / max_y * 230:.1f}' r='6'>"
        f"<title>{escape(name)}: {x:.2f} tok/s, {y:.2f} ms</title></circle>"
        for name, x, y in points
    )
    return _svg(dots, "Throughput versus time to first token", "Throughput (tok/s)", "TTFT (ms)")


def _svg(content: str, label: str, x_label: str, y_label: str) -> str:
    return (
        f"<svg viewBox='0 0 600 310' role='img' aria-label='{escape(label)}'>"
        "<path d='M40 20V280H580' fill='none' stroke='#94a3b8'/>"
        f"<text x='310' y='305' text-anchor='middle'>{escape(x_label)}</text>"
        f"<text x='14' y='155' text-anchor='middle' transform='rotate(-90 14 155)'>{escape(y_label)}</text>"
        + content
        + "</svg>"
    )


def _empty(message: str) -> str:
    return f"<p class='muted'>{escape(message)}</p>"


def _width(value: float, values: list[tuple[str, float]]) -> float:
    low = min(score for _, score in values)
    high = max(score for _, score in values)
    return 70 if high == low else 10 + (value - low) / (high - low) * 60
