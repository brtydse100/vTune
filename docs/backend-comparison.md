# GuideLLM and vLLM comparison

This procedure compares the two HTTP benchmark clients against the same
vLLM server. It uses the fixed [four-prompt dataset](assets/backend-comparison.jsonl),
one request at a time, greedy sampling, and a fixed eight-token output budget.
Run each client against a freshly restarted server with the same model and
server flags. Keep both raw JSON files; never compare a hand-normalized copy.

## Recorded settings

| Setting | Value |
| --- | --- |
| Dataset | `docs/assets/backend-comparison.jsonl`, four prompts in file order |
| Endpoint | `/v1/completions` on `127.0.0.1:8000` |
| Requests | 4, `max_requests=4` / `num-prompts=4` |
| Concurrency | 1 (`synchronous` / `max-concurrency=1`) |
| Arrival | Immediate (`request-rate=inf`) |
| Sampling | `temperature=0`, `top_p=1` |
| EOS | `ignore_eos=true` in both clients |
| Output | 8 requested tokens per request |
| Server | Same model, vLLM flags, port, and environment for both runs |

## Run

From the repository root on native Linux, set an absolute model path and create
an empty evidence directory:

```bash
MODEL=/models/your-model
rm -rf comparison-evidence
mkdir -p comparison-evidence/guidellm comparison-evidence/vllm
```

Restart the same server before each client. Save the server log separately for
each run. Then execute:

```bash
vllm serve "$MODEL" --host 127.0.0.1 --port 8000 \
  > comparison-evidence/guidellm/vllm.log 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
guidellm run \
  --backend '{"kind":"openai_http","target":"http://127.0.0.1:8000","model":"'"$MODEL"'","request_format":"/v1/completions","extras":{"body":{"temperature":0,"top_p":1,"ignore_eos":true}}}' \
  --profile kind=synchronous \
  --constraint kind=max_requests,count=4 \
  --data kind=json_file,path=docs/assets/backend-comparison.jsonl \
  --output kind=json,path=comparison-evidence/guidellm/results.json
kill "$SERVER_PID"; wait "$SERVER_PID" 2>/dev/null || true
trap - EXIT
```

Repeat the server start with its log redirected to `vllm/vllm.log`, then run:

```bash
vllm serve "$MODEL" --host 127.0.0.1 --port 8000 \
  > comparison-evidence/vllm/vllm.log 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
vllm bench serve --backend vllm --model "$MODEL" \
  --host 127.0.0.1 --port 8000 --endpoint /v1/completions \
  --dataset-name custom --dataset-path docs/assets/backend-comparison.jsonl \
  --num-prompts 4 --max-concurrency 1 --request-rate inf \
  --custom-output-len 8 --temperature 0 --top-p 1 --ignore-eos \
  --save-result --result-dir comparison-evidence/vllm \
  --result-filename results.json --disable-tqdm
kill "$SERVER_PID"; wait "$SERVER_PID" 2>/dev/null || true
trap - EXIT
```

## Compare

Record the installed vLLM, GuideLLM, Python, model, GPU, and server flags next
to the evidence. Compare these fields without silently changing definitions:

| Canonical unit | GuideLLM source | vLLM source |
| --- | --- | --- |
| Request total | `request_totals` | `num_prompts` |
| Successful/failed | `request_totals.successful`, `.errored`, `.incomplete` | `completed`, `failed`, and `num_prompts` |
| Requests/s | `requests_per_second` | `request_throughput` |
| Output tokens/s | `output_tokens_per_second` | `output_throughput` |
| TTFT | `time_to_first_token_ms` | `mean_ttft_ms` and percentile fields |
| End-to-end latency | `request_latency` converted seconds to milliseconds | `mean_e2el_ms` and percentile fields |

GuideLLM and vLLM may differ in measurement-window boundaries, request
scheduling overhead, token counting, and percentile implementation. Report
those differences beside the raw values. A matching request total is necessary
but does not make latency or throughput definitions identical.
