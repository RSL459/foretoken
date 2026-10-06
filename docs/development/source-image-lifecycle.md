<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Runtime source lifecycle

English | [简体中文](source-image-lifecycle_zh.md)

Source updates separate application code from its runtime dependencies. For installation and update commands, see [Deploy Foretoken from Source](../custom-deployment.md).

## Preparation and publication

The CLI owns checkout bindings, installation settings and input snapshots on the workstation. Source operations are serialized per cluster on that workstation and synchronize changed files and deletions before building.

BuildKit Pods compile applications with persistent caches, separate from model storage. Each component is prepared once for its runtime environment rather than once per model namespace. Before reusing compiler output, a source operation stops abandoned publisher Jobs from the same binding.

Application files are published to a platform-owned HTTP service and volume. The publisher runs on the file server's node, so ReadWriteOnce storage can serve workloads on other nodes; BuildKit Pods do not mount that volume. Publication completes atomically before workloads select a version. Published files remain immutable.

## Engine source and native extensions

An explicit engine checkout is independent of the pinned vLLM Rust dependency. Python modules come from that checkout with Foretoken's patches applied; the runtime supplies compatible native libraries and generated dependencies. Deleted source files must not reappear from the image's older package.

Native extensions use the selected runtime's Python, PyTorch and accelerator libraries with upstream incremental caches. MetaX native updates select the compiled plugin rather than its precompiled kernel package. Dependency updates retain compatibility with these accelerator libraries.

## Workload activation

The CLI selects source revisions on services; controllers own frontend rollout and model Pool/Group replacement. Model preparation and all serving members, including LWS leaders and workers, use the same file selection. A download init container prepares application files in Pod-local storage, independently of RuntimeCache or shared model volumes.

Workloads start the downloaded executable with its matching Python and engine paths. Application files are read-only; model data, runtime caches and profiling output use separate writable storage.

For source updates, Helm selects control-plane files, downloaded before CRD bootstrap and manager startup. Saved video-task plans retain their application version for execution and cleanup. The CLI checks actual runtime images, source versions, complete serving membership, routing state and Service endpoints before reporting success. Controllers own route withdrawal and request draining.

## Environment updates and cleanup

Runtime dependency, image recipe and Helm changes use the platform installation lifecycle. A successful full source installation clears previous service source selections and the control-plane file selection so workloads use the newly built images.

Cleanup retains versions referenced by service intent, Pool/Group templates, preparation Jobs, running or terminating workloads, saved video-task plans and Helm rollback history. A publisher removes only its own binding's unreferenced versions, preserving other publishers' in-flight files.

Helm owns the file service and publication volume. Source uninstall removes managed compiler caches and the workstation binding without deleting model data. vLLM-Omni uses a separate [image build recipe](../custom-deployment.md#vllm-omni-runtime).
