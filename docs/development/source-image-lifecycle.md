<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Source deployment lifecycle

English | [简体中文](source-image-lifecycle_zh.md)

This guide describes the behavior to preserve when maintaining source deployments. For commands and examples, see [Deploy Foretoken from Source](../custom-deployment.md).

## Installation and updates

`foretoken install -e .` updates the shared controller, CRDs and runtime defaults. `foretoken deploy` builds from the selected checkout and updates only the submitted services.

Source updates reuse compatible runtime environments and rebuild them automatically when dependency or base-image inputs change. The CLI remembers engine directories separately for each Foretoken source directory. Engine source must remain compatible with the selected Python, PyTorch and accelerator libraries.

## Builds and publication

Rebuild the application parts affected by a change and preserve source deletions. Publish a complete application before updating its services; running services must not depend on writable compiler caches.

Independent source directories can build concurrently. Serialize source preparation and submission within one source directory, and keep platform installation and removal exclusive. Waiting for service readiness must not prevent deletion from releasing occupied devices.

Deployment succeeds when the selected application and its serving routes are ready. Controllers manage rollout and request draining.

## Cleanup

Keep applications still needed by deployments, builds or rollback. Preserve recoverable build inputs before releasing unused resources.

`foretoken delete` removes the selected deployment and cleans up build resources no longer in use, preserving source directories, experiment results and source archives. Uninstall the shared platform after its services have been deleted; model data and archived inputs are retained.
