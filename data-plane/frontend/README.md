<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Foretoken Frontend

English | [简体中文](README_zh.md)

The frontend provides one entry point for deployed text and video models. Text requests return a complete response or stream output as it is generated. Video requests can save the generated video directly to a file.

## Connect to a service

Follow the repository [Quick Start](../../README.md#quick-start) to deploy a service, then run these commands from the repository root to get its frontend address:

```bash
DEPLOYMENT=examples/quickstart
FRONTEND_URL="$(foretoken endpoint "$DEPLOYMENT")"
REQUEST_HOST="$(foretoken endpoint "$DEPLOYMENT" --host)"
```

The requests below include a `Host` header and work with either LoadBalancer or [Gateway](../../README.md#gateway-mode) access. Configure TLS and authentication at the cluster ingress.

## Generate text

Select the model through `model`. This request uses the Quick Start's `Qwen/Qwen3-0.6B`:

```bash
curl --fail-with-body "$FRONTEND_URL/v1/chat/completions" \
  -H "Host: $REQUEST_HOST" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "Qwen/Qwen3-0.6B",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 512
  }'
```

The default response is JSON. Add `"stream": true` to the request and `--no-buffer` to `curl` to receive output as it is generated.

### Choose an API

| API | Path | Request input |
| --- | --- | --- |
| OpenAI Chat Completions | `POST /v1/chat/completions` | `model`, `messages` |
| OpenAI Responses | `POST /v1/responses` | `model`, `input`; set `store: false` and send the conversation history on each turn |
| Anthropic Messages | `POST /v1/messages` | `model`, `messages`, and a required `max_tokens` budget |
| Anthropic token counting | `POST /v1/messages/count_tokens` | The same model, messages, system prompt, and tools used for generation |
| Text completions | `POST /v1/completions` | `model`, `prompt` |

`GET /v1/models` lists model identifiers. `/tokenize` and `/detokenize` convert between text and token IDs.

Tools run in the client, which sends their results in the next request. Responses supports function tools, namespaced functions, and unconstrained custom-text tools. It does not support server-hosted tools or the Responses background mode. Forced tool choice and strict tool schemas require structured-output support in the model service.

Thinking controls depend on the model's chat template. Output budgets include reasoning tokens; Messages uses `max_tokens` and does not accept a separate `thinking.budget_tokens`. When the budget is exhausted, Messages reports `max_tokens` and Responses reports `incomplete`. Tool calls may be unfinished; execute only complete calls.

Image-capable text models accept base64 image `data:` URLs rather than remote image URLs.

## Generate video

After deploying the [MiniMax H3 recipe](../../examples/recipes/minimax-h3/a100-bf16-tp2/README.md), send a local reference image and save the generated video as an MP4 file in one request.

Set `REFERENCE_IMAGE` to an existing PNG on the client machine, then run from the repository root:

```bash
DEPLOYMENT=examples/recipes/minimax-h3/a100-bf16-tp2
REFERENCE_IMAGE=/path/to/reference.png
FRONTEND_URL="$(foretoken endpoint "$DEPLOYMENT")"
REQUEST_HOST="$(foretoken endpoint "$DEPLOYMENT" --host)"
curl --fail --max-time 4000 \
  "$FRONTEND_URL/v1/videos/sync" \
  -H "Host: $REQUEST_HOST" \
  -F model=MiniMaxAI/MiniMax-H3 \
  -F 'prompt=A sailboat crossing a calm bay at sunrise' \
  -F "input_reference=@${REFERENCE_IMAGE};type=image/png" \
  -F width=1024 -F height=576 -F num_frames=124 -F fps=24 \
  -F num_inference_steps=50 -F aspect_ratio=16:9 -F flow_shift=12 -F seed=1 \
  -F 'extra_params={"task":"fl2va","audio_flow_shift":3}' \
  --output video.mp4
```

The generated video is saved as `video.mp4` in the current directory. For video-conditioned generation, see the H3 recipe.

### Submit now and retrieve later

Use `/v1/videos` when the client needs to disconnect after submission. This stores the task and its result on the service. Enable it in the deployment's `frontend.yaml`:

```yaml
spec:
  videoTasks:
    claimName: video-results
    retentionSeconds: 86400
```

`video-results` must be an existing persistent volume claim (PVC) in the same namespace, separate from the model cache. Frontend replicas and task workers need access to it; use shared ReadWriteMany storage across nodes. Place the reference image at `inputs/reference.png` in this volume, then apply the configuration:

```bash
foretoken deploy "$DEPLOYMENT" --timeout 1h
```

Input paths are relative to the volume root, not the client machine. Submit with the ModelService name `h3`, rather than the model repository ID:

```bash
curl --fail-with-body "$FRONTEND_URL/v1/videos" \
  -H "Host: $REQUEST_HOST" \
  -H 'Content-Type: application/json' \
  -d '{
    "modelServiceRef": {"name": "h3"},
    "request": {
      "task": "fl2va",
      "prompt": "A sailboat crossing a calm bay at sunrise",
      "width": 1024, "height": 576,
      "numFrames": 124, "fps": 24, "numInferenceSteps": 50,
      "inputFiles": [{
        "field": "input_reference",
        "path": "inputs/reference.png",
        "contentType": "image/png"
      }]
    }
  }'
```

A successful submission returns HTTP `202` with `id`, `status_url`, and `content_url`. Use the same frontend address for subsequent calls, replacing `{id}` with the returned task ID:

| Action | Endpoint | When to use it |
| --- | --- | --- |
| Check status | `GET /v1/videos/{id}` | `Pending`, `Starting`, and `Running` mean work is not complete; for `Failed`, read `reason` and `message` |
| Save the video | `GET /v1/videos/{id}/content` | After `phase` becomes `Succeeded`, save the response with `curl --output video.mp4` |
| Cancel | `POST /v1/videos/{id}/cancel` | After HTTP `202`, continue checking until a terminal state; backend computation may still be finishing |
| Delete | `DELETE /v1/videos/{id}` | After HTTP `202`, the service removes the task and its files |

The configuration above retains results for one day after a task ends, then removes them automatically. Original reference files in `inputs/` are retained.

## Operations

| Endpoint | Purpose |
| --- | --- |
| `/healthz` | Frontend process liveness |
| `/readyz` | Readiness to accept generation requests |
| `/statusz` | Serving and cache-index status |
| `/metrics` | Prometheus metrics |

Access to operator endpoints follows the cluster's network policy. Gateway exposes the client paths `/v1`, `/tokenize`, and `/detokenize`.

Use `foretoken status` to inspect a deployment and `foretoken delete` to remove it, passing its configuration directory to either command.
