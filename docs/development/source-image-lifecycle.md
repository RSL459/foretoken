<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Source deployment lifecycle

English | [简体中文](source-image-lifecycle_zh.md)

This guide describes the behavior to preserve when maintaining source deployments. For commands and examples, see [Deploy Foretoken from Source](../custom-deployment.md).

## Installation and updates

`foretoken install -e .` updates the shared controller, CRDs and runtime defaults. `foretoken deploy` builds from the selected checkout and updates only the submitted services.

Source changes reuse the existing runtime environment; dependency or base-image changes require rebuilding it. The CLI remembers each checkout's engine directories. Engine source must remain compatible with the selected Python, PyTorch and accelerator libraries.

## Builds and publication

Rebuild the application parts affected by a change and preserve source deletions. Publish a complete application before updating its services; running services must not depend on writable compiler caches.

Installation automatically prepares persistent node-local compiler storage. Builder replacement preserves its caches, while application and model storage keep their existing configuration and permissions.

Separate worktrees can build concurrently. Serialize source preparation and submission within one checkout, and keep platform installation and removal exclusive. Waiting for service readiness must not prevent deletion from releasing occupied devices.

Deployment succeeds when the selected application and its serving routes are ready. Controllers manage rollout and request draining.

## Cleanup

Failure or cancellation stops the operation's builders and publishers, preserving compiler storage for recovery. Keep applications still needed by workloads or rollback.

Deleting a candidate removes its deployment, not the shared platform. Uninstall the platform after its services have been deleted; reclaim compiler volumes before removing their storage provisioner, and retain model data.
