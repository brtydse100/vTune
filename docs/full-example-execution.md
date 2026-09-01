# Execution, logging, and summaries

```yaml
execution:
  mode: sequential       # Default. Alternative: local_parallel; see below.
  host: 127.0.0.1       # Interface used by readiness and GuideLLM.
  health_path: /health  # vLLM readiness endpoint.
  shutdown_grace: 15    # Seconds allowed for owned processes to stop.
  retry:
    max_attempts: 2     # Default: 1. Only transient failures are retried.

  # To run independent trials concurrently, replace mode and add:
  # mode: local_parallel
  # max_parallel_trials: 2
  # gpu_allocation:
  #   strategy: explicit       # Optional; explicit is the only current strategy.
  #   allow_sharing: false     # Optional; sharing is intentionally unsupported.
  #   workers:
  #     - name: worker-0
  #       devices: [0, 1]
  #     - name: worker-1
  #       devices: [2, 3]
  # ports:
  #   min: 8100
  #   max: 8199
  # Remove server.port and CUDA_VISIBLE_DEVICES from env/tune_env in this mode;
  # The vllm-opt CLI assigns both. Each trial's tensor-parallel-size must fit a worker.

logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR, or CRITICAL. Default: INFO.

# Optional: create a concise OpenAI-compatible summary in report.html.
# Export the key before running; the vllm-opt CLI never saves the key in YAML or artifacts.
# HTTPS is required except for localhost, 127.0.0.0/8, or ::1. Redaction is
# name-based and cannot guarantee arbitrary values contain no secrets.
# analysis:
#   llm_summary:
#     base_url: https://api.example.com/v1
#     model: your-model
#     api_key_env: VLLM_OPTIMIZER_LLM_API_KEY
#     timeout: 30
```
