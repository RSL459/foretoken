<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Profiling

English | [简体中文](README_zh.md) · [Evaluation and profiling](../../README.md)

Capture a short CPU/GPU execution timeline to locate bottlenecks. Profiling requires a [source-installed CLI and platform](../../../docs/custom-deployment.md). The Quick Start already supplies persistent storage for captures.

## Capture a benchmark workload

Run from the repository root:

```bash
foretoken perf examples/quickstart \
  --profile --profile-engine pytorch --profile-duration 15s \
  --num-prompts 2 --max-tokens 128 --output local
```

This records up to 15 seconds of PyTorch execution on NVIDIA or [MetaX GPUs](../../../docs/metax-deployment.md), stopping earlier when the workload finishes. Use a Foretoken Kustomize directory to select the service, and `--model` for a multi-model deployment. Profiling adds overhead; measure latency and throughput in a separate run without `--profile`.

Generated requests, trace replay, conversations, mixed datasets, SLO probes, and HTTP sweeps can all accompany a capture. Each sweep repetition saves its own `profile.json` in its result directory.

## Inspect results

On the computer running your browser, use a kubeconfig for the target cluster:

```bash
foretoken profile view
```

Open the printed URL and select a capture. PyTorch traces open in Perfetto, so the browser needs access to `ui.perfetto.dev`. Nsight timelines open in the official NVIDIA viewer via “Open in NVIDIA Nsight Systems”. Perfetto-compatible mcTracer JSON opens in Perfetto.

Ctrl+C closes the viewer. Capture files remain available for later viewing and download, including after a temporary benchmark deployment is removed.

## Deploy and capture external traffic

```bash
foretoken deploy examples/quickstart \
  --profile --profile-engine pytorch --profile-duration 15s --timeout 20m
```

Capture starts when the service is ready; send traffic from another client during the recording window. The service remains running afterwards. Repeat the command to capture another window.

## MetaX mcTracer

The model-server image needs the MACA SDK's matching `mcTracer` executable on `PATH` and `libmcpti.so`. Add this under `spec` in your ModelService YAML:

```yaml
profiling:
  engine: mctracer
```

Use `foretoken deploy` to apply the setting to an existing service, then run the benchmark or external-traffic capture with `--profile-engine mctracer`. CUDA Graph can remain enabled. The YAML selects the tool prepared at model startup; the capture flag selects that same tool. Without the YAML setting, the model prepares PyTorch.

## Nsight Systems

Nsight Systems captures CUDA and NVTX activity on NVIDIA GPUs. It uses a diagnostic image and a deployment selecting `spec.profiling.engine: nsight`.

### Prepare the diagnostic image

After source installation, build the Linux x86_64 image from your local model-server image. Set `NSIGHT_IMAGE` to a registry reference you can push and your cluster can pull:

```bash
docker build -f deploy/inference-engines/nsight/Dockerfile \
  --build-arg MODEL_SERVER_IMAGE=foretoken-dev-model-server \
  -t "$NSIGHT_IMAGE" deploy/inference-engines/nsight
docker push "$NSIGHT_IMAGE"
```

Save this as `nsight-values.yaml`, replacing `YOUR_NSIGHT_IMAGE` with that reference:

```yaml
runtime:
  vllm:
    nsightImage: YOUR_NSIGHT_IMAGE
```

Add `--values nsight-values.yaml` to the source installation command used for this cluster. Only models selecting Nsight use the diagnostic image.

### Capture

The [Nsight example](../../../examples/profile/nsight/README.md) selects the tool and persistent storage:

```bash
foretoken perf examples/profile/nsight \
  --profile --profile-engine nsight --profile-duration 15s \
  --num-prompts 2 --max-tokens 128 --output local
```

Use the viewer above to open the timeline. For external traffic, replace `examples/quickstart` with `examples/profile/nsight` and `pytorch` with `nsight` in the deploy command. Changing a deployment's profiler replaces its model processes; apply that change before capturing an existing service.

## Clean up

Delete the retained deployment and capture records when no longer needed:

```bash
foretoken delete examples/quickstart
```

Use `examples/profile/nsight` instead for the Nsight example.
