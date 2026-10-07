# Foretoken

English | [简体中文](README_zh.md)

Foretoken deploys and manages generative inference services on Kubernetes, with request routing, autoscaling, evaluation, and observability across NVIDIA and MetaX GPUs.

## Features and Status

| Capability | Guide | Status |
| --- | --- | --- |
| Route requests using load and KV cache locality | [Routing](data-plane/frontend/src/router/README.md) | Research |
| Adjust model capacity to demand | [Autoscaling](docs/autoscaling.md) | In development |
| Serve with separate encoder, prefill, and decode stages | [E/P/D example](examples/encoder-prefill-decode/README.md) | Research |
| Measure performance and answer quality | [Benchmarks](benchmarks/README.md) | In development |
| Inspect CPU/GPU execution | [Profiling](benchmarks/docs/profile/README.md) | In development |
| View metrics, logs, and alerts | [Observability](observability/README.md) | In development |

## Quick Start

This example serves `Qwen/Qwen3-0.6B` on a local NVIDIA GPU using k3d. Prepare a Linux host with Python 3.11+, Docker, NVIDIA Container Toolkit, k3d, kubectl, and Helm; see [k3d setup](docs/k3d-deployment.md). The model requests one GPU, 4 CPUs, and 48 GiB of host memory.

For another environment, use the [Kubernetes](docs/kubernetes-deployment.md), [kind](docs/kind-deployment.md), or [MetaX](docs/metax-deployment.md) guide.

### Install and deploy

```bash
git clone https://github.com/shiweijiezero/foretoken.git
cd foretoken
pip install -e .

# Select GPU 0 from nvidia-smi.
foretoken cluster create k3d --name foretoken-dev --gpus 0
foretoken install -e .
foretoken deploy examples/quickstart --timeout 20m
```

Wait for the frontend and model service to report Ready, then send a request:

```bash
FORETOKEN_FRONTEND_URL="$(foretoken endpoint examples/quickstart)"

curl --fail-with-body --no-buffer \
  "$FORETOKEN_FRONTEND_URL/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen/Qwen3-0.6B","messages":[{"role":"user","content":"Hello"}],"stream":true}'
```

The answer streams to your terminal. The [frontend guide](data-plane/frontend/README.md) covers other APIs and admission settings.

### Measure performance

```bash
foretoken perf examples/quickstart --num-prompts 20 --output local
```

Inspect latency, throughput, and request success in the summary. Continue with [performance workloads](benchmarks/docs/perf/README.md), [quality evaluation](benchmarks/docs/eval/README.md), or [profiling](benchmarks/docs/profile/README.md).

### Update the service

After editing the source or deployment configuration, rerun `foretoken deploy examples/quickstart --timeout 20m`. See [source deployment](docs/custom-deployment.md) for engine changes and [the CLI guide](cli/README.md) for published installations.

## Gateway Mode

For a shared hostname-based entry point, follow [Gateway setup](cli/README.md#gateway-mode).

## Stop and Uninstall

```bash
foretoken delete examples/quickstart
foretoken uninstall
foretoken cluster delete k3d --name foretoken-dev
```

For an existing cluster, omit the last command. Platform removal preserves log storage and reused installations.

## Related Projects

- [vLLM](https://github.com/vllm-project/vllm)
- [NVIDIA Dynamo](https://github.com/ai-dynamo/dynamo)
- [llm-d](https://github.com/llm-d/llm-d)
- [AIBrix](https://github.com/vllm-project/aibrix)
- [vLLM Production Stack](https://github.com/vllm-project/production-stack)

## Contributing

Contributions to code, documentation, testing, and design are welcome. See [Contributing](CONTRIBUTING.md) for the development and review process.

Thank you to everyone who has contributed to Foretoken.

<a href="https://github.com/shiweijiezero/foretoken/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=shiweijiezero/foretoken" width="256" alt="Foretoken contributors" />
</a>

## License

[Apache License 2.0](LICENSE).
