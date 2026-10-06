<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Runtime source lifecycle

English | [简体中文](source-image-lifecycle_zh.md)

Source updates separate application code from its runtime dependencies. For installation and update commands, see [Deploy Foretoken from Source](../custom-deployment.md).

## Preparation and publication

The CLI owns checkout bindings, installation settings and input snapshots on the workstation. Source operations are serialized per cluster on that workstation and synchronize changed files and deletions before building.

BuildKit Pods compile applications with persistent caches, separate from model storage. Interrupted installations retain these caches. Before reusing compiler output, a source operation stops abandoned publisher Jobs from the same binding. Temporary registry Secrets belong to their build Pods.

Control-plane executables and CRDs are published to a platform-owned HTTP service and volume. The publisher runs on the file server's node and releases its mount before rollout; BuildKit Pods do not mount that volume. Complete versions are published atomically and remain immutable. Consumers download the selected version before startup.

Frontend and model-server payloads are published to the workload's persistent cache. Publication completes before a service selects the revision. The publisher uses the runtime image's user and runs separately from serving Pods.

## Engine source and native extensions

An explicit engine checkout is independent of the pinned vLLM Rust dependency. Python modules come from that checkout with Foretoken's patches applied; the runtime supplies compatible native libraries and generated dependencies. Deleted inputs disappear from later payloads, while Python-only updates retain successful native builds.

Native extensions use the selected runtime's Python, PyTorch and accelerator libraries with upstream incremental caches. Image builds package the prepared source and resolve its dependencies while retaining the accelerator ABI. MetaX native updates select the compiled plugin rather than its precompiled kernel package.

## Workload activation

The CLI selects a source revision on each service; controllers own frontend rollout and model Pool/Group replacement. Model preparation and serving use the same selection. The image bootstrap activates its executable, Python adapters and engine payload. A declared but missing executable fails startup.

The CLI verifies selected workloads, active source, routing state and Service endpoints before reporting success. Controllers own admission, route withdrawal and request draining; frontend acknowledgement of an empty routing snapshot remains independent of serving readiness.

## Image updates and cleanup

Data-plane bootstrap, dependency, image recipe and Helm changes use the platform installation lifecycle. Runtime updates also use images when writable storage is unavailable or a single-node claim awaits its first placement; model preparation owns that placement. A successful source installation clears service source selections and the control-plane file selection so workloads use the newly built images.

Control-plane cleanup retains versions referenced by Helm history, workload templates, running Pods and saved VideoTask plans. Runtime cleanup retains service selections, templates and running or terminating consumers across namespaces sharing a data directory. Both remove only their binding's unreferenced publications.

Runtime build volumes follow the model cache's lifecycle; Helm owns the control-plane file service and volume. Source uninstall removes managed compiler caches and the workstation binding without deleting model data. vLLM-Omni uses a separate [image build recipe](../custom-deployment.md#vllm-omni-runtime).
