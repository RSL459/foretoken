<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Source deployment lifecycle

English | [简体中文](source-image-lifecycle_zh.md)

For installation, deployment and parallel candidate commands, see [Deploy Foretoken from Source](../custom-deployment.md). This guide describes the responsibilities to preserve when changing that workflow.

## Installation and deployment

Platform installation owns the shared controller, CRDs and runtime defaults. Deployment builds frontend and model-server code from the selected checkout and applies it only to the submitted services. Keeping these operations separate prevents one candidate from changing the platform used by others.

The CLI records engine directory choices per checkout and includes source deletions when preparing a build. Deleted engine files must not reappear from the base image. Builds must remain compatible with the selected Python and accelerator libraries.

## Concurrent builds

Serialize source preparation and service submission for the same checkout. Other checkouts can build concurrently, while platform installation and uninstall exclude those operations. Release source-operation locks before waiting for readiness so deletion can free devices for an unscheduled service.

Compiler caches are reusable build inputs, not serving state. Coordinate access through the builder, and keep mutable source and export directories from being overwritten by another candidate. Before reusing outputs, stop abandoned publishers that might still read or write them.

## Serving and cleanup

Publish the environment image and complete application files together in an immutable manifest at the trusted application origin. Controllers resolve and save that selection before creating workloads, so preparation, serving, restarts and scaling use the same code without rereading the manifest. Report deployment success only after that code and its serving routes are ready; rollout and draining remain controller-owned.

Application storage belongs to the platform. Cleanup preserves publications referenced by services, workloads, saved tasks or Helm rollback history, and removes only the publisher's unreferenced files. Candidate deletion removes its deployment, not the shared platform. Uninstall releases managed build resources and local source records while preserving model data.
