<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Source update lifecycle

English | [简体中文](source-image-lifecycle_zh.md)

Installation and update commands are in [Deploy Foretoken from Source](../custom-deployment.md). The following constraints apply when maintaining the update path.

## Build and publish

Platform installation owns the shared controller, CRDs and runtime defaults. Source deployment selects the current Foretoken Git checkout, or an explicit `-e PATH`, and builds only frontend and model-server environments and applications. It must not reinstall the platform or publish candidate control-plane changes.

Each checkout owns its source state, build binding, compiler cache and remembered engine paths. Builds and service submissions on the same checkout serialize; different checkouts can build and deploy concurrently. Readiness waits hold no source-operation lock, allowing completed candidates to be deleted to release capacity. A new worktree does not inherit another worktree's engine paths. Build workspaces, daemon storage and exports remain separate, even when candidates share a registry or platform application storage.

Synchronization includes file deletions; engine updates must not restore deleted source from the runtime image. Compiler caches are separate from model data, and compilation preserves compatibility with the selected runtime's Python and accelerator libraries.

A complete application version is published before use and remains immutable. Stop a build's abandoned publishers before reusing its output. The platform owns application storage independently of compiler and model caches.

## Select and recover

Each source publication records its environment image alongside its files in the trusted origin's immutable manifest. Services select a publication, not an arbitrary image or download URL. Controllers resolve and save that selection before creating workloads; retained selections do not depend on fetching the manifest again. Model preparation and serving use the same version; restarts and scaling retain it. Platform installation updates defaults without replacing existing service selections.

Deployment success requires the selected version and serving routes to be ready. Existing controllers own rollout and request draining. Namespaces separate candidate services and routing; GPU requests and node selectors use the existing Kubernetes scheduler and device plugins.

## Clean up

Keep versions referenced by services, workload templates, running or terminating workloads, saved tasks and Helm rollback history. Remove only the publisher's unreferenced versions, leaving other publishers' work intact.

Deleting a candidate removes its deployment, not the shared platform. Helm owns application storage. Source uninstall removes managed compiler caches and workstation bindings while preserving model data.
