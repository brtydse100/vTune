# Compatibility

vLLM Config Tuner targets Python 3.11–3.12 and Linux experiment hosts with NVIDIA GPUs.

Verified combinations:

| vLLM | GuideLLM | Environment |
| --- | --- | --- |
| 0.28.0 | 0.7.3 | WSL2, RTX 3080 |

Both GuideLLM 0.7.3 and `vllm bench serve` from vLLM 0.28.0 are supported.
Workload arguments are passed through, so consult the documentation for the
installed engine version when adopting newer options.

On the verified WSL2 host, vLLM 0.28.0 needed these server environment values:

```yaml
env:
  VLLM_USE_V2_MODEL_RUNNER: "0"
  VLLM_USE_FLASHINFER_SAMPLER: "0"
```

The first disables a runner that required unavailable unified virtual
addressing; the second avoids a sampler requiring a local CUDA compiler.
Native Linux systems may not need either setting.

## CUDA compatibility

vLLM Config Tuner does not bundle CUDA and does not require one exact CUDA release. The
working combination is determined by vLLM, its PyTorch wheel, the NVIDIA
driver, the GPU architecture, and any locally compiled kernels. Therefore,
vLLM Config Tuner cannot promise support for every CUDA version.

Follow the [vLLM GPU installation guide](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/)
for the vLLM release you install. Also check NVIDIA's
[CUDA compatibility table](https://docs.nvidia.com/deploy/cuda-compatibility/minor-version-compatibility.html):
newer CUDA toolkits require a sufficiently recent driver, and some PTX or new
features require a newer driver even within a compatible major family.

The `py3-none-any` wheel is one universal pure-Python artifact for Linux,
Windows, and macOS. It is not three OS-specific binaries. Native vLLM execution
is unsupported on Windows; configuration and stored-result inspection work.
