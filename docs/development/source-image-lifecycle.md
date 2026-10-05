<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Runtime source lifecycle

English | [简体中文](source-image-lifecycle_zh.md)

Source updates separate application code from its runtime dependencies. For installation and update commands, see [Deploy Foretoken from Source](../custom-deployment.md).

## Preparation and publication

The CLI saves checkout bindings and installation settings on the workstation. Source operations are serialized per cluster on that workstation and synchronize changed files and deletions before building.

BuildKit Pods compile applications with persistent caches, separate from model storage. Application files are published to a platform-owned HTTP service and volume. The publisher runs on the file server's node, so ReadWriteOnce storage can serve workloads on other nodes; BuildKit Pods do not mount that volume.

Publication completes atomically before workloads select a version. Published files are immutable. Before reusing compiler output, a source operation stops any abandoned publisher Jobs from the same binding.

## Engine source and native extensions

An explicit engine checkout is independent of the pinned vLLM Rust dependency. Python modules come from that checkout with Foretoken's engine patches applied. The selected runtime supplies compatible native libraries and generated dependencies. Deleted source files must not reappear from the image's older package.

Native extensions build against the selected runtime's Python, PyTorch and accelerator libraries, using upstream incremental caches. MetaX builds select the compiled plugin rather than its precompiled kernel package. Dependency updates retain compatibility with these accelerator libraries.

## Workload activation

Controllers record the selected runtime image and application version in service status before creating workloads. Recovery and scaling, including recovery from zero replicas, retain that selection. Model preparation and all serving members use the same version.

A download init container prepares application files in Pod-local storage. Workloads start the downloaded executable with its matching Python and engine paths. Application files are read-only; model data, runtime caches and profiling output use separate writable storage.

Helm manages the control-plane update, with application files and CRDs prepared before startup. The CLI reports deployment success after verifying the selected runtime, serving replicas, routing readiness and Service endpoints. Controllers retain responsibility for request draining during replacement.

## Environment updates and cleanup

Runtime dependency, image recipe and Helm configuration changes use the platform installation lifecycle. Platform updates change defaults for new services; redeployment selects the current runtime and application files for existing services. Image-only services retain that mode until redeployed.

Cleanup retains versions referenced by service selections, workload templates, saved task plans, running or terminating workloads, and Helm rollback history. A publisher removes only its own unreferenced versions, preserving other publishers' in-flight files.

Helm owns the file service and publication volume. Source uninstall removes managed compiler caches and the workstation binding without deleting model data. vLLM-Omni uses a separate [image build recipe](../custom-deployment.md#vllm-omni-runtime).
