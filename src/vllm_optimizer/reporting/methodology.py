"""Metric definitions shown in the self-contained report."""


def metric_methodology() -> str:
    return """<section><h2>How metrics are calculated</h2>
<dl class='definitions'>
<dt>Requests/s</dt><dd>Completed requests divided by the benchmark measurement time.</dd>
<dt>Output tokens/s</dt><dd>Generated output tokens divided by measurement time. Total tokens/s includes prompt and output tokens.</dd>
<dt>TTFT</dt><dd>Time from sending a request until its first generated token.</dd>
<dt>TPOT</dt><dd>Average time per generated output token after the first token.</dd>
<dt>ITL</dt><dd>Delay between consecutive streamed output tokens.</dd>
<dt>E2E latency</dt><dd>Time from request start until the complete response is received.</dd>
<dt>Average / median / P99</dt><dd>Arithmetic mean, 50th percentile, and 99th percentile. P99 means 99% of observations were at or below that value.</dd>
<dt>Elapsed</dt><dd>vLLM Optimizer wall-clock time from benchmark subprocess launch through JSON result parsing; vLLM server startup is measured separately.</dd>
</dl>
<p class='note'>The benchmark backend calculates request distributions and percentiles. vLLM Optimizer maps backend names and units into one schema without deriving missing percentiles. For scoring, eligible workloads are averaged within a benchmark execution, repeated executions use their median score, and named benchmark scores are averaged into the trial score.</p></section>"""
