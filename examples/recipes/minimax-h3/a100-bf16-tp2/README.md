<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# MiniMax H3 BF16 on two NVIDIA A100 GPUs

English | [简体中文](README_zh.md)

Deploy native-BF16 MiniMax H3 with TP=2 on two A100 80 GB GPUs.
Video requests enter the standard Foretoken frontend; the Omni adapter owns
internal engine execution and lifecycle.

The same recipe serves FL2VA or Ref2VA; select the partition before deployment.

## Build and install

Prepare a working Foretoken cluster using the [k3d guide](../../../../docs/k3d-deployment.md).
Allow at least 256 GiB of host memory and enough cache capacity for the selected weights.
From the Foretoken repository root:

```bash
make image-vllm-omni VLLM_OMNI_IMAGE=foretoken-vllm-omni:h3
make image-model-server-omni \
  INFERENCE_ENGINE_IMAGE=foretoken-vllm-omni:h3 \
  OMNI_MODEL_SERVER_IMAGE=foretoken-omni-model-server:h3
```

The engine build pins public vLLM-Omni revision
`ad025defe68a46bdc3590c53161889aa6932ff4c` and `vllm/vllm-openai:v0.30.0`.
Source and dependencies are installed inside the image, not copied from a host
checkout or Conda environment. No unpublished H3 patches are required.
Use `VLLM_OMNI_BASE_IMAGE` for an immutable base-image digest when required.

For k3d, import the images into your own cluster (`CLUSTER` from the k3d guide):

```bash
k3d image import --cluster "$CLUSTER" foretoken-omni-model-server:h3
```

For other clusters, push the Omni image to a registry reachable by the nodes.
Select it in `platform-values.yaml` using the existing platform setting:

```yaml
runtime:
  vllmOmni:
    image: foretoken-omni-model-server:h3
```

```bash
foretoken install -e . --values platform-values.yaml
```

The standard source installer builds and distributes the platform images.
For a remote cluster, add `--registry` as described in the
[source deployment guide](../../../../docs/custom-deployment.md).

## Deploy and request

The default source is the public Hugging Face repository `MiniMaxAI/MiniMax-H3`.
`spec.engineArgs.task-type` in `model.yaml` selects `fl2va` (default) or `ref2va`
through the upstream loader. The repository ID stays the same for either partition.
Foretoken provides the configured model cache; first startup downloads the weights.
Login is optional, not a prerequisite.

Set `cache.yaml` to a data directory available on the GPU node, following
[model storage](../../../../docs/model-storage.md). RuntimeCache selects a cache
root, not a model component directory.

### FL2VA (default)

Prepare a local reference PNG and set `REFERENCE_IMAGE` to its path:

```bash
RECIPE=examples/recipes/minimax-h3/a100-bf16-tp2
REFERENCE_IMAGE=/path/to/reference.png
foretoken deploy "$RECIPE" --timeout 1h
ENDPOINT="$(foretoken endpoint "$RECIPE" --timeout 10m)"
curl --fail-with-body --max-time 4000 \
  -X POST "${ENDPOINT%/}/v1/videos/sync" \
  -F model=MiniMaxAI/MiniMax-H3 \
  -F 'prompt=A cinematic tracking shot of a sailboat crossing a calm bay at sunrise.' \
  -F "input_reference=@${REFERENCE_IMAGE};type=image/png" \
  -F width=1024 -F height=576 -F num_frames=124 -F fps=24 \
  -F num_inference_steps=50 -F aspect_ratio=16:9 -F flow_shift=12 -F seed=1 \
  -F 'extra_params={"task":"fl2va","audio_flow_shift":3}' \
  --output h3-fl2va.mp4
```

The recipe includes a `FrontendService`. Endpoint discovery uses the normal
LoadBalancer/Gateway access modes, without exposing the internal ModelGroup
Service. The controller derives TP=2 from the requested two GPUs.

The frontend and Omni synchronous-request budgets are 4000 seconds.
`OMNI_VIDEO_SYNC_TIMEOUT` sets Omni's HTTP deadline and whole-request worker RPC
budget when building the adapter image. `timeouts.drain` is a separate
Pod-shutdown budget.

### Reference-video generation

For Ref2VA, change `spec.engineArgs.task-type` in `model.yaml` to `ref2va`,
then deploy the same recipe again. With only two GPUs available, delete the
existing deployment first to release its GPUs. Let in-flight requests finish
before switching. Existing weights remain in the cache.
Prepare a local reference MP4 and set `REFERENCE_VIDEO` to its path:

```bash
RECIPE=examples/recipes/minimax-h3/a100-bf16-tp2
REFERENCE_VIDEO=/path/to/reference.mp4
foretoken delete "$RECIPE" --timeout 2h
foretoken deploy "$RECIPE" --timeout 1h
ENDPOINT="$(foretoken endpoint "$RECIPE" --timeout 10m)"
curl --fail-with-body --max-time 4000 \
  -X POST "${ENDPOINT%/}/v1/videos/sync" \
  -F model=MiniMaxAI/MiniMax-H3 \
  -F 'prompt=Continue the scene shown in the reference video with a smooth camera movement.' \
  -F "input_references=@${REFERENCE_VIDEO};type=video/mp4" \
  -F width=1024 -F height=576 -F num_frames=124 -F fps=24 \
  -F num_inference_steps=50 -F aspect_ratio=16:9 -F flow_shift=12 -F seed=1 \
  -F 'extra_params={"task":"ref2va","audio_flow_shift":3}' \
  --output h3-ref2va.mp4
```

The request task must match the deployed partition. Reference media processing
stays in vLLM-Omni; Foretoken forwards the multipart input through its standard
router. To switch back, delete the deployment, set `task-type: fl2va`, and redeploy
before using the FL2VA request above.

Both partitions have completed real generation through the standard frontend
on two A100 80 GB GPUs, using native BF16, TP=2, 50 diffusion steps,
1024x576 resolution, 124 frames, and 24 FPS. The returned videos passed full
decoding and sampled-frame inspection. Generation reused cached original HF
weights; source-download checks covered configuration files from HF, ModelScope,
and an HF-compatible mirror, not fresh full-weight downloads.

## Other sources

ModelScope hosts H3 under a different repository name. To use it, change these
fields in `model.yaml` and use `MiniMax/MiniMax-H3` in the request's `model` field:

```yaml
spec:
  model: MiniMax/MiniMax-H3
  source: modelscope
```

Keep the selected `task-type`. The image includes the ModelScope SDK; the upstream
loader downloads the selected partition into the same configured RuntimeCache.
The Hugging Face mirror setting below does not apply to ModelScope.

For a Hugging Face-compatible mirror, use the existing platform setting:

```yaml
runtime:
  vllm:
    modelSource:
      endpoint: https://your-huggingface-compatible-mirror.example
```

The controller projects this endpoint only to Hugging Face workloads. The mirror
must provide the repository and revision; a failed download does not switch sources.

For optional offline/pre-downloaded weights, select `source: local` and set
`model` to the mounted checkpoint root or selected partition directory, following
[model sources](../../../../docs/model-sources.md). Use the same identity in the
multipart `model` field. Optional authentication for download quotas uses the
normal platform Secret configuration, not image layers.

```bash
foretoken delete "$RECIPE" --timeout 2h
```

Deleting the deployment retains the configured model cache.
