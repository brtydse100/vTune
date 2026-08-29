# Compatibility

vTune `0.1.0a1` targets Python 3.11–3.12 and Linux experiment hosts with NVIDIA
GPUs.

Verified combinations:

| vLLM | GuideLLM | Environment |
| --- | --- | --- |
| 0.10.2 | 0.7.3 | WSL2, RTX 3080 |
| 0.28.0 | 0.7.3 | WSL2, RTX 3080 |

On the verified WSL2 host, vLLM 0.28.0 needed these server environment values:

```yaml
server:
  env:
    VLLM_USE_V2_MODEL_RUNNER: "0"
    VLLM_USE_FLASHINFER_SAMPLER: "0"
```

The first disables a runner that required unavailable unified virtual
addressing; the second avoids a sampler requiring a local CUDA compiler.
Native Linux systems may not need either setting.

The `py3-none-any` wheel is one universal pure-Python artifact for Linux,
Windows, and macOS. It is not three OS-specific binaries. Native vLLM execution
is unsupported on Windows; configuration and stored-result inspection work.
