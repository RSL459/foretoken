# Foretoken

English | [简体中文](README_zh.md)

Foretoken is a generative inference orchestration framework built for SLO/SLA targets and heterogeneous accelerators.

Built on inference engines such as vLLM and SGLang, Foretoken organizes multiple generation instances into a cluster service for request routing, autoscaling, instance management, and benchmarking.
We aim to turn an inference cluster into a token factory that continuously converts compute into tokens while meeting latency and quality requirements.

## When to Use Foretoken

- Serve one or more models across multiple GPUs and Kubernetes nodes. Each ModelGroup currently runs on one node; a service scales across nodes by creating additional groups.
- Route requests based on load, queue depth, or KV cache state.
- Autoscale inference instances based on traffic and SLO targets.
- Compare aggregated serving, Prefill/Decode disaggregation, and different parallelism strategies.
- Use the same orchestration stack across NVIDIA, MetaX, Huawei Ascend, and other accelerators.

If you only need to serve a single model on one GPU, using an inference engine such as vLLM directly is usually enough.

## Features and Status

| Feature | Description | Status |
|---|---|---|
| Benchmarking | Performance benchmarks and parameter sweeps, correctness evaluation, and SLO simulation | In development |
| Profiling | Use PyTorch Profiler and Nsight to identify compute, communication, and CPU/GPU bottlenecks | Planned |
| Hardware support | Common interfaces for device capabilities, runtimes, communication, and metrics | In development |
| Request routing | Select instances based on load, queues, KV reuse, and service levels | Research |
| Distributed inference | Aggregated serving, Prefill/Decode disaggregation, and WideEP parallelism | Research |
| Control plane | Model services, instance groups, autoscaling, updates, and failure recovery | Planned |
| Deployment and observability | Kubernetes deployment, metrics, dashboards, and alerts | Planned |

## Quick Start

### 1. Install Foretoken

Local mode runs the frontend without installing or requiring a cluster Gateway:

```bash
helm upgrade --install foretoken \
  oci://ghcr.io/shiweijiezero/foretoken/charts/foretoken \
  --namespace foretoken-platform \
  --create-namespace \
  --set frontend.enabled=true \
  --set frontend.mode=local \
  --wait
```

### 2. Deploy a model service

`examples/quickstart/kustomization.yaml` is the deployment entrypoint. It organizes the frontend and model services, while the Operator creates and manages the underlying resources.

```bash
FORETOKEN_NAMESPACE=foretoken-demo
FORETOKEN_SERVING_DIR=examples/quickstart

# Create the namespace for the model service; keep it unchanged if it exists.
kubectl create namespace "${FORETOKEN_NAMESPACE}" \
  --dry-run=client -o yaml | kubectl apply -f -

# Apply the model service configuration; the Operator creates and starts its workloads.
kubectl apply --server-side \
  --namespace "${FORETOKEN_NAMESPACE}" \
  -k "${FORETOKEN_SERVING_DIR}"
```

### 3. Wait for serving to become ready

```bash
FORETOKEN_NAMESPACE=foretoken-demo
FORETOKEN_SERVING_DIR=examples/quickstart

# Wait until the frontend and model services in the Kustomize entrypoint are ready.
kubectl kustomize "${FORETOKEN_SERVING_DIR}" |
  kubectl wait --for=condition=Ready \
    --namespace "${FORETOKEN_NAMESPACE}" \
    --timeout=15m \
    -f -
```

### 4. Send a generation request

Start the local access helper from the source checkout. It waits for the frontend and reconnects after Pod replacement or transport interruption:

```bash
./scripts/foretoken-port-forward \
  --namespace foretoken-demo \
  --frontend quickstart-frontend \
  --local-port 8080
```

Keep the helper running and send the request from another terminal:

```bash
curl --fail-with-body --no-buffer \
  http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"quickstart-qwen3-0.6b","messages":[{"role":"user","content":"Hello"}],"stream":true}'
```

The Operator manages the underlying resources; local mode keeps access private to the cluster unless the user opens a port-forward.

## Production Gateway Access

Production mode creates an `HTTPRoute` for an existing Gateway API `Gateway`. Configure the Gateway and set `spec.hostname` on each `FrontendService`:

```bash
helm upgrade --install foretoken \
  oci://ghcr.io/shiweijiezero/foretoken/charts/foretoken \
  --namespace foretoken-platform \
  --create-namespace \
  --set frontend.enabled=true \
  --set frontend.mode=production \
  --set frontend.gateway.name=inference-gateway \
  --set frontend.gateway.namespace=gateway-system \
  --wait
```

Set the public hostname in the frontend manifest:

```yaml
spec:
  hostname: foretoken.example.com
```

The Gateway must allow `HTTPRoute` resources from the namespaces where Foretoken frontends run. DNS and TLS remain owned by the platform Gateway.

## Stop and Uninstall

Delete the serving configuration so the Operator can stop the service and clean up its resources:

```bash
FORETOKEN_NAMESPACE=foretoken-demo
FORETOKEN_SERVING_DIR=examples/quickstart

kubectl delete --wait=true --timeout=10m \
  --namespace "${FORETOKEN_NAMESPACE}" \
  -k "${FORETOKEN_SERVING_DIR}"
```

After the serving resources are gone, uninstall Foretoken:

```bash
helm uninstall foretoken \
  --namespace foretoken-platform \
  --wait --timeout 5m
```

Uninstalling the control plane preserves Foretoken CRDs and custom resources. Delete the CRDs explicitly only after all Foretoken resources have been removed:

```bash
kubectl delete crd \
  frontendservices.inference.foretoken.io \
  modelservices.inference.foretoken.io \
  modelpools.inference.foretoken.io \
  modelgroups.inference.foretoken.io
```

## Install from Source

Use the local Chart from a source checkout:

```bash
helm upgrade --install foretoken ./deploy/charts/foretoken \
  --namespace foretoken-platform \
  --create-namespace \
  --wait
```

## Related Projects

- [vLLM](https://github.com/vllm-project/vllm)
- [NVIDIA Dynamo](https://github.com/ai-dynamo/dynamo)
- [llm-d](https://github.com/llm-d/llm-d)
- [AIBrix](https://github.com/vllm-project/aibrix)
- [vLLM Production Stack](https://github.com/vllm-project/production-stack)

## Contributing

Contributions to deployment baselines, hardware support, benchmarking, routing and autoscaling algorithms, tests, and documentation are welcome.
Performance-related changes should include the test setup, raw results, and reproducible commands.
See [Contributing to Foretoken](CONTRIBUTING.md) for development principles, collaboration expectations, and the pull request workflow.

## License

This project is licensed under the [Apache License 2.0](LICENSE).
