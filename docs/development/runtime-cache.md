<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Maintain runtime storage

English | [简体中文](runtime-cache_zh.md)

RuntimeCache provides persistent model files and engine caches to model-server and frontend. For deployment settings and prepared model directories, see [Model storage](../model-storage.md).

## Change storage provisioning

The RuntimeCache controller owns the PVC, its capacity, and readiness. Workload controllers mount the published claim. An administrator-supplied `workload.cache.claimName` takes precedence and remains externally managed.

For directory storage, the CLI resolves the node-visible path and creates a static PV matching the controller-created PVC. Keep claim names, volume names, access modes, and binding capacity in the controller; the CLI consumes that selection. Directory binding capacity is not a filesystem quota.

Local k3d mounts and single-node directories use PV node affinity. A multi-node absolute path must already expose the same shared filesystem on every node; directory provisioning does not transfer files or install shared storage.

Dynamic storage uses a StorageClass. With `maxSize`, the controller requests expansion when any observed mount has at most 20% free space, doubling the requested capacity up to that limit. A failed expansion can leave the already-bound volume usable; inspect the RuntimeCache condition and PVC events to distinguish expansion failure from binding failure.

## Preserve data across deletion and redeployment

With `Retain`, the controller releases PVC ownership when the RuntimeCache is deleted. It can adopt an unchanged directory claim with matching path, binding, and ownership. Namespace deletion still removes the PVC.

The CLI retains directory PVs by default. After the old claim is gone, redeployment can bind the same PV to the new PVC. Rebinding checks the resource version and old claim before updating; another deployment's volume, or a changed path or node placement, requires a new cache name.

With `retentionPolicy: Delete`, the controller requests PVC deletion and Kubernetes waits for workloads to release it. The CLI then deletes its directory PV object. Directory files remain because that PV uses `Retain`; dynamic volumes follow their StorageClass reclaim policy.

## Change cache locations

Keep prepared models under `models` and provider caches under their upstream layouts, including `models/hub`. The shared artifacts resolver locates local model and tokenizer directories without changing the public model identifier. It keeps relative references inside the model root and rejects individual files. Downloading and format validation belong to the engine and tokenizer loaders.

Engine caches use `vllm`, `torch`, and `triton` below the data root. Triton uses `triton/<node-name>` to separate node writes and reuse files after Pod replacement. Cache location changes take effect through a Group rollout; existing Groups retain their environment until replaced. Compiler subdirectories remain engine-managed.

Profiling captures use `profiles/runs` under the same persistent root; see [Profiling](../../benchmarks/docs/profile/README.md). Persistent model paths do not add namespace or Pod identities.

## Diagnose temporary-cache use

If persistent cache preparation or its write probe fails during startup, a single-node model-server stops the failed EngineCore before retrying once under the Pod's `/tmp`. Multi-node members restart as a complete Group rather than retrying independently. A frontend missing a Hub snapshot can use temporary tokenizer storage.

Temporary retry starts a new engine; it does not redirect a running engine or copy prepared checkpoints. Local models still resolve from the persistent model root, and profiling captures are unavailable during the retry. Check model-server logs and `foretoken_runtime_cache_temporary` to identify this mode, then repair the persistent volume before restarting the workload.
