<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Deploy Foretoken from Source

[English](custom-deployment.md) | [中文](custom-deployment_zh.md)

Build Foretoken from a local checkout and deploy source changes to Kubernetes.

## Install from source

Prepare Python 3.11+, Git, kubectl, and Helm. The cluster must allow BuildKit Pods and publishing Jobs, with a default StorageClass for compiler caches and published application files. To override their storage classes, set `development.build.storageClassName` or `applicationFiles.storageClassName` in `deploy/platform-values.yaml` and pass it with `--values`.

```bash
git clone https://github.com/shiweijiezero/foretoken.git
cd foretoken
kubectl config current-context
```

Install the CLI from this checkout:

```bash
pip install -e .
```

For a local kind or k3d cluster, build and install without a registry:

```bash
foretoken install -e .
```

The same command can switch a CLI-managed release installation to this source checkout. Builds run in the cluster. For GPU setup in k3d, see [Deploy Foretoken with k3d](k3d-deployment.md).

## Deploy and update code

Deploy the maintained [Quick Start](../README.md#quick-start) on a GPU-enabled cluster:

```bash
foretoken deploy examples/quickstart --timeout 20m
```

On a source-installed platform, deployment builds from the Foretoken Git checkout containing the current directory. After editing it, run the same command again. To select a checkout from another directory, use `foretoken deploy examples/quickstart -e /path/to/foretoken --timeout 20m`; the Kustomize path still resolves from the current directory.

Deployment builds and selects the frontend and model-server runtime for these services without reinstalling the shared controller or CRDs. Changes to platform code or configuration require an explicit `foretoken install -e .`. Code updates restart affected workloads and may reload model weights. Use the Quick Start's [request](../README.md#4-send-a-test-request) and [cleanup](../README.md#stop-and-uninstall) commands.

Changes to CLI Python files take effect from the checkout where the CLI was installed with `pip install -e .`; reinstall when its Python dependencies change.

### Run candidates in separate worktrees

Install the shared platform once using the source installation above. Each worktree has its own source state and compiler cache, so different worktrees can build and deploy concurrently. Give each candidate its own Kubernetes namespace to keep its model services and frontend separate.

From the repository root, create one candidate and a Kustomize overlay of the Quick Start:

```bash
git worktree add ../candidate-a -b experiment/candidate-a
cd ../candidate-a
mkdir -p examples/candidate
cat > examples/candidate/kustomization.yaml <<'EOF'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
namespace: candidate-a
resources:
  - ../quickstart
patches:
  - target:
      kind: ModelService
    patch: |-
      - op: replace
        path: /spec/resources/requests/gpu/count
        value: 2
      - op: replace
        path: /spec/engineArgs/tensor-parallel-size
        value: 2
  - target:
      kind: RuntimeCache
    patch: |-
      - op: replace
        path: /spec
        value:
          initialSize: 20Gi
          accessMode: ReadWriteOnce
          retentionPolicy: Delete
EOF

foretoken deploy examples/candidate --timeout 20m
foretoken perf examples/candidate --num-prompts 20 \
  --output experiment --output-dir results/candidates --iteration candidate-a
```

This example dynamically provisions a PVC for each candidate, avoiding per-worktree host mounts; to reuse an existing model directory, see [model storage](model-storage.md).

Repeat with different worktree, branch, namespace and iteration names for the other candidates. Eight such deployments request 16 GPUs: each has one single-node model replica requesting two GPUs and explicitly configured for tensor parallelism of two. The cluster also needs enough CPU, memory and platform capacity. If placement matters, add `spec.nodeSelector` to the model configuration; it selects nodes, not particular GPU indices. Use exclusive GPU resources rather than time-sliced replicas for independent physical devices.

Keep measurements and output directories within each worktree; use the [experiment records guide](../rsi-playbooks/experiment-records.md) to compare results. Shared CPU, storage and network activity can still affect measurements. Updating a fully occupied GPU cluster can temporarily stop the old candidate while its replacement acquires those devices.

Delete only the candidate's deployment when finished:

```bash
foretoken delete examples/candidate
```

Uninstall the platform only after all candidates have finished.

## Edit an inference engine

To modify vLLM, bind a Git checkout matching the runtime's Python, PyTorch, and accelerator environment. For a checkout at `../vllm`:

```bash
foretoken deploy examples/quickstart --engine-source ../vllm --timeout 20m
```

The engine selection is remembered for this worktree. Other worktrees do not inherit its engine paths; select their engine checkouts explicitly when needed. After editing Python, Triton or NVIDIA CUDA/C++ source, rerun `foretoken deploy`; required compilation is automatic. Registry and platform settings come from the shared installation.

For MetaX, native kernels belong to the plugin checkout. Bind it alongside the matching core checkout:

```bash
foretoken deploy examples/quickstart \
  --engine-source ../vllm \
  --engine-source vllm-metax=../vllm-metax --timeout 20m
```

### Select a different runtime environment

A standard deployment does not require changing the base image. The default image includes the Python, PyTorch, CUDA, and vLLM components needed to run the model service.

To use a custom environment, edit `baseImage` in [`deploy/inference-engines/vllm/source-environment.json`](../deploy/inference-engines/vllm/source-environment.json):

```json
{"baseImage": "ghcr.io/example/custom-vllm:latest"}
```

Source installs, `make image-model-server`, `deploy/dev-build`, and release builds all use this setting. The image must be compatible with Foretoken's vLLM adapter and accessible to the builder. After changing it in an existing source installation, run `foretoken deploy` again.

To override the base for one installation instead, set `runtime.vllm.image` in `deploy/platform-values.yaml`:

```yaml
runtime:
  vllm:
    image: ghcr.io/example/custom-vllm:latest
```

Reapply the installation command with `--values deploy/platform-values.yaml`, retaining the registry and engine-source options. With `-e`, Foretoken uses this image as its build base. Set the field to `auto` to restore automatic runtime selection. Then deploy the workload again.

MetaX base-image builds are covered by [Prepare Foretoken for MetaX GPUs](development/metax-platform.md#install-from-source).

### vLLM-Omni runtime

vLLM-Omni uses a separate model-server image. Build it from the repository root on a machine with Docker BuildKit, Make, and a rustup-managed Rust toolchain:

```bash
make image-vllm-omni VLLM_OMNI_IMAGE=foretoken-vllm-omni:latest
make image-model-server-omni \
  INFERENCE_ENGINE_IMAGE=foretoken-vllm-omni:latest \
  OMNI_MODEL_SERVER_IMAGE=foretoken-omni-model-server:latest
```

For k3d, set `CLUSTER` to the existing cluster name and import the image:

```bash
CLUSTER=foretoken-qwen-test
k3d image import --cluster "$CLUSTER" foretoken-omni-model-server:latest
```

For a remote cluster, use the `REGISTRY` configured in the [Kubernetes deployment guide](kubernetes-deployment.md). Log in first when that registry requires authentication:

```bash
docker tag foretoken-omni-model-server:latest "$REGISTRY/omni-model-server:latest"
docker push "$REGISTRY/omni-model-server:latest"
```

Set `runtime.vllmOmni.image` in `deploy/platform-values.yaml` to the image the nodes can pull. This example uses the local image; for a registry, replace it with the full pushed reference:

```yaml
runtime:
  vllmOmni:
    image: foretoken-omni-model-server:latest
```

Apply the runtime setting:

```bash
foretoken install -e . --values deploy/platform-values.yaml
```

Retain `--registry "$REGISTRY"` for remote platform builds and any other installation options. The editable vLLM source path above targets the standard vLLM backend.

After installation, run `foretoken deploy` with the Kustomize directory for your Omni service. For code updates, rebuild and distribute the Omni image, then set `runtime.vllmOmni.image` to a new tag or digest reference. Reapply the installation command and deploy the same Kustomize directory again.
