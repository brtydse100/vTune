# Parallel trials

Parallel mode runs several independent vLLM configurations at once on one
Linux or WSL host. It is different from `tensor-parallel-size`, which divides
one vLLM instance across several GPUs.

## Configuration

```yaml
execution:
  mode: local_parallel
  max_parallel_trials: 2
  gpu_allocation:
    strategy: explicit
    allow_sharing: false
    workers:
      - name: worker-0
        devices: [0, 1]
      - name: worker-1
        devices: [2, 3]
  ports:
    min: 8100
    max: 8199
```

`strategy` and `allow_sharing` may be omitted because their shown values are
the only currently supported behavior. In this first implementation,
`max_parallel_trials` must equal the number of declared workers so no worker is
silently ignored. The port range must contain at least one port per worker.

Do not set `server.port`, tune `port`, or set/tune `CUDA_VISIBLE_DEVICES` in
parallel mode. The `vtune` CLI owns those values to prevent collisions. Worker names and
GPU sets must be unique, and GPU sets cannot overlap.

## Scheduling behavior

- The baseline runs alone on one compatible worker.
- The coordinator suggests each unique configuration and assigns it to a free
  worker whose GPU count can satisfy its `tensor-parallel-size`.
- Random and TPE can have several pending trials. The coordinator alone updates
  Optuna when results return; workers never write optimizer state.
- A failed trial releases only its own worker. Other trials continue.
- Cancelling the experiment cancels every active trial manager, which cleans
  its owned vLLM and GuideLLM process groups.
- Each trial stores its resolved assignment as a typed `execution` object:
  mode for every trial, plus worker name, integer physical GPU identifiers,
  and port for parallel trials. a5/a6 runs may lack this data.

## Interpreting results

Parallel trials can contend for CPU, RAM, storage bandwidth, PCIe/NVLink,
network capacity, power, and cooling. That contention can change latency and
throughput. Reports therefore label parallel measurements and warn that the
baseline ran alone.

Use parallel mode to search faster, then rerun important finalists sequentially
before making production decisions. Automatic sequential finalist validation,
automatic GPU allocation, GPU sharing, heterogeneous GPU comparison, and
multi-host execution remain roadmap work.
