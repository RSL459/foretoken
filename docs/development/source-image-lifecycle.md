<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Runtime source lifecycle

English | [简体中文](source-image-lifecycle_zh.md)

Source updates separate application code from the image supplying its dependencies. Installation and redeployment commands are in [Deploy Foretoken from Source](../custom-deployment.md).

## Preparation and publication

The CLI owns the workstation's checkout binding, saved installation settings, and input comparison. The binding identifies the cluster and installed platform; it is not shared between workstations. Source operations serialize by cluster on the workstation. Added and changed files and removals update the cluster workspace before compilation.

Dedicated BuildKit Pods retain compiler volumes separately from model data. Dockerfile export targets produce application executables; Python adapters and selected engine sources complete the payload. Go, Cargo, and native build tools own their incremental caches. A component is prepared once for the selected environment, rather than once per model namespace.

The platform owns a separate publication volume and HTTP service. A short-lived publisher Job shares the origin's node and reads the compiler output, so RWO storage can serve consumers on other nodes. Cached BuildKit Pods never mount the publication volume. The Job publishes through staging and rename, shares unchanged files with the previous version, and finishes before workload activation. Its deadline and retention use the caller's timeout. A subsequent source operation stops its binding's abandoned Jobs before reusing compiler output.

Published directories are immutable. Cleanup preserves current bundle selections, Service intent, Pool and Group templates, preparation Jobs, running or terminating consumers, Helm rollback history, and VideoTask plans. It only removes the current binding's unreferenced publications. Another publisher's in-flight files are not retired.

## Engine source and native extensions

An explicit engine checkout is independent of the pinned vLLM Rust dependency. Python modules come from that checkout; compatible native libraries and generated or vendor files absent from it come from the selected runtime. Foretoken's engine patches remain applied. Deleted source files must not reappear through the image's older Python package.

Native builds use the selected runtime's Python, PyTorch, and accelerator environment, adding compiler tools in a separate build stage. Upstream build tools retain their own incremental caches. MetaX native updates select the compiled plugin rather than its precompiled kernel package. Environment changes use the normal package resolver and retain the selected accelerator ABI dependencies.

## Workload activation

The CLI selects source revisions on services. Controllers own frontend rollout, ModelPool/ModelGroup replacement, and the matching preparation and serving workloads. A download init container prepares the selected application in Pod-local storage; application code does not require RuntimeCache or a shared model volume. LWS leaders and workers inherit the same file selection.

Workloads start the downloaded executable directly. The executable activates its Python and engine paths without selecting another binary from an older image. The application mount is read-only; model data, runtime compilation and profiling output retain their existing writable storage. Model preparation reads the selected Python provider file rather than a separately embedded copy.

The control plane follows the same download-before-start order for its executables and CRDs. Helm owns its selection and rollout, while video-worker plans retain the file version needed for later execution and cleanup.

The CLI verifies the selected runtime image and source, the complete serving cohort, consumed routing version, and Service endpoints before reporting success. Platform image changes do not advance Service generation, so an old Ready condition alone does not prove that the selected version is running. Controllers retain their existing route withdrawal, request drain, and resource release responsibilities.

## Environment updates and cleanup

Changes to runtime dependencies, image recipes, or Helm configuration use the platform installation lifecycle. Registry builds push image outputs directly from the cluster; local kind/k3d builds load them into node containerd without routing archives through the client. Image reuse compares actual build output with installed references.

A successful full source installation clears the previous source and control-plane file selections in favor of its newly built images. The platform file origin follows the Helm release. Source uninstall removes managed compiler caches and the workstation binding without deleting model data. vLLM-Omni retains its separate [image build recipe](../custom-deployment.md#vllm-omni-runtime).
