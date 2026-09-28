<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Foretoken Frontend

The frontend serves OpenAI Chat Completions, OpenAI Responses, and Anthropic Messages at one address. Requests select a configured model through the `model` field.

## Send a request

Deploy the repository [Quick Start](../../README.md#quick-start), which includes a Chat Completions example. From the repository root, use the same deployment for Responses or Messages:

```bash
FRONTEND_URL="$(foretoken endpoint examples/quickstart)"

# OpenAI Responses
curl --fail-with-body "$FRONTEND_URL/v1/responses" \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3-0.6B","input":"Hello","max_output_tokens":512,"store":false}'

# Anthropic Messages
curl --fail-with-body "$FRONTEND_URL/v1/messages" \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen/Qwen3-0.6B","messages":[{"role":"user","content":"Hello"}],"max_tokens":512}'
```

These requests return JSON. Add `"stream": true` to receive incremental server-sent events (SSE), and use `curl --no-buffer` to display them as they arrive.

## Choose an API

| API | POST path | Conversation input |
| --- | --- | --- |
| OpenAI Chat Completions | `/v1/chat/completions` | `messages` |
| OpenAI Responses | `/v1/responses` | `input`; set `store: false` and send the conversation history on each turn |
| Anthropic Messages | `/v1/messages` | `messages` and a required `max_tokens` output budget |
| Anthropic token counting | `/v1/messages/count_tokens` | `messages`, with the same system prompt and tools as generation |

`GET /v1/models` lists the configured model identifiers. Text completions use `POST /v1/completions`; `/tokenize` and `/detokenize` convert between text and token IDs.

Tools run in the client, which sends their results in the next request. Responses supports function tools, namespaced functions, and unconstrained custom-text tools. Server-hosted tools and background responses are unsupported.

Forced tool choice and strict tool schemas require structured-output support in the model service. Thinking controls depend on the model's chat template. Output budgets include reasoning tokens; Messages uses `max_tokens` for the total budget and does not accept a separate `thinking.budget_tokens` allowance.

When the output budget is exhausted, Messages reports `max_tokens` and Responses reports `incomplete`. Execute only complete tool calls; interrupted calls may be omitted or contain partial arguments.

Image-capable model services accept base64 image `data:` URLs rather than remote image URLs.

## Asynchronous video tasks

To keep generation running after a client disconnects, enable video tasks on the FrontendService. Choose a dedicated PVC in the same namespace that can be mounted by its frontend replicas and task workers. For replicas on different nodes, use shared ReadWriteMany storage. This storage is separate from the model cache.

```yaml
spec:
  videoTasks:
    claimName: video-results
    retentionSeconds: 86400
```

Reapply the deployment with `foretoken deploy`. Place reference files in the volume's `inputs/` directory, then submit a request naming the ModelService. Generation currently uses the synchronous video transport's 48 MiB multipart request limit, including reference files. For example, for the H3 recipe and `inputs/reference.png`:

```bash
RECIPE=examples/recipes/minimax-h3/a100-bf16-tp2
FRONTEND_URL="$(foretoken endpoint "$RECIPE")"
REQUEST_HOST="$(foretoken endpoint "$RECIPE" --host)"
curl --fail-with-body "$FRONTEND_URL/v1/videos" \
  -H "Host: $REQUEST_HOST" \
  -H 'Content-Type: application/json' \
  -d '{
    "modelServiceRef":{"name":"h3"},
    "request":{"task":"fl2va","prompt":"A sailboat at sunrise","width":1024,"height":576,"numFrames":124,"fps":24,"numInferenceSteps":50,"inputFiles":[{"field":"input_reference","path":"inputs/reference.png","contentType":"image/png"}]}
  }'
```

A successful submission returns `202` with an `id`, `status_url`, and `content_url`. Copy that ID into `TASK_ID`:

```bash
TASK_ID=video-UUID-from-response
curl --fail-with-body -H "Host: $REQUEST_HOST" "$FRONTEND_URL/v1/videos/$TASK_ID"
# Once phase is Succeeded:
curl --fail-with-body -H "Host: $REQUEST_HOST" \
  "$FRONTEND_URL/v1/videos/$TASK_ID/content" --output video.mp4
```

Task phases are `Pending`, `Starting`, `Running`, `Succeeded`, `Failed`, and `Cancelled`. State and results are shared across replicas of the same FrontendService. Input copies and generated results expire after the configured retention interval; original files in `inputs/` remain available. Interrupted execution is reported as failed rather than automatically generating a second video.

Use `POST /v1/videos/{id}/cancel` to stop waiting for an active generation, or `DELETE /v1/videos/{id}` to remove the task and its stored files. Cancellation terminates the worker request; backend computation may continue until the engine observes disconnection. Access to tasks is scoped to the FrontendService, with authentication managed at the cluster ingress.

## Access and operations

The default endpoint uses a Kubernetes LoadBalancer. For hostname-based access, see [Gateway mode](../../README.md#gateway-mode). Configure TLS and authentication at the cluster's ingress.

| Endpoint | Purpose |
| --- | --- |
| `/healthz` | Frontend process liveness |
| `/readyz` | Frontend readiness to accept requests |
| `/statusz` | Serving and cache-index diagnostics |
| `/metrics` | Prometheus metrics |

Access to operator endpoints follows the cluster's network policy; Gateway mode exposes the client paths `/v1`, `/tokenize`, and `/detokenize`.

After changing a service configuration, reapply it with `foretoken deploy`. Use `foretoken status` to inspect it and `foretoken delete` to remove it, passing the same configuration directory to each command.
