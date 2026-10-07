<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Model storage

[中文](model-storage_zh.md)

Model deployments reuse downloaded weights and runtime caches through persistent storage. The Quick Start already configures its cache; deploy it without creating another storage configuration:

```bash
foretoken deploy examples/quickstart --timeout 20m
```

On local k3d, it uses the repository-root `data/` directory mounted by `foretoken cluster create`. On other clusters, the relative directory in `cache.yaml` becomes a dynamic PVC with an initial size of 10 GiB. A single schedulable node uses `ReadWriteOnce`; multiple nodes use `ReadWriteMany`, which the StorageClass must support.

## Select a StorageClass and capacity

For dynamic storage, replace the `spec` in the example's `cache.yaml` with:

```yaml
spec:
  initialSize: 10Gi
  accessMode: ReadWriteMany
```

Use a size that accommodates your models. Add `storageClassName` to choose a StorageClass, or use `ReadWriteOnce` when all consumers run on one node. Add `maxSize` to enable automatic expansion if the driver supports online expansion.

To use a PVC managed elsewhere, set `workload.cache.claimName` in platform values and provide that claim in each workload namespace.

## Use a prepared directory

Set `spec.directory` in `cache.yaml` to a directory readable and writable by the frontend and model Pods. On local k3d, paths are relative to the Kustomize directory: `../../data` in the Quick Start points to the repository-root `data/`. The host directory must be mounted into the k3d nodes; see the [k3d guide](k3d-deployment.md).

On a remote cluster, use an absolute path that already exists on the target node or at the same location on every participating node's shared filesystem. Foretoken does not upload the local directory. Directory storage is configured without PVC size or StorageClass fields:

```yaml
spec:
  directory: /var/lib/foretoken/data
  accessMode: ReadWriteMany
```

Set storage choices before the first deployment. Changing a bound cache's directory, StorageClass, initial size, or access mode requires a new RuntimeCache name; use `maxSize` for expansion. Move or copy existing files separately if needed. To load a prepared checkpoint below `data/models/`, follow [model sources](model-sources.md#use-a-local-model-directory).

## Keep or remove cache data

Directory-backed files remain after `foretoken delete`. Dynamic cache PVCs default to `retentionPolicy: Retain`; set `retentionPolicy: Delete` in `cache.yaml` to remove the claim with the cache. Deleting an example namespace also deletes its PVCs, and the volume's reclaim policy determines whether the underlying data remains.

Profiling captures use the same data root under `profiles/`; see [Profiling](../benchmarks/docs/profile/README.md).

## Share downloads and loaded weights between nodes

To share public model downloads through Dragonfly, save this in `deploy/platform-values.yaml`:

```yaml
modelDistribution:
  dragonfly:
    enabled: true
```

Apply it to a published installation:

```bash
foretoken install --values deploy/platform-values.yaml
```

For a source installation, use `foretoken install -e . --values deploy/platform-values.yaml`, retaining the registry and engine-source options. Redeploy model services to use the updated settings.

Installation prepares Dragonfly or reuses an existing release. To select a particular release, add `existingRelease: {name: dragonfly, namespace: dragonfly-system}` under `modelDistribution.dragonfly`. Authenticated models and custom model endpoints download directly from their provider.

On NVIDIA clusters with allocated RDMA devices, ModelExpress can load weights from running replicas. Add this alongside the Dragonfly setting:

```yaml
modelDistribution:
  modelexpress:
    enabled: true
```

Automatic weight transfer applies to remote models with a persistent cache, data parallelism of one, and fixed expert placement. An explicit `load-format` remains unchanged; replicas without a compatible source load the prepared files. Reapply the installation and redeploy after changing either setting. Both features are disabled by default; set `enabled: false` to turn one off.
