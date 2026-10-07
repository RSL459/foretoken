<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# CI Guidelines

English | [简体中文](ci_zh.md)

CI prepares execution environments, invokes existing repository checks and selected feature tests, and reports results. For example, the data-plane workflow calls `make verify-data-plane`; it does not maintain another Rust verification implementation.

Start with the [local checks](testing.md#run-the-relevant-checks), then validate changed CI wiring in an authorized run. Syntax checks alone do not establish that triggers, runner permissions, or artifact transfer work; report any unexecuted part.

## Agree on automation before adding it

Inspect the current workflow and its owning commands. Identify the basic check, key feature, or release artifact, what existing execution misses, the automation's value, runtime and resource cost, and who will diagnose failures. Prefer adjusting an existing task. Obtain maintainer approval before adding permanent jobs, workflows, matrix dimensions, or scheduled runs. Features, bug fixes, temporary incidents, and one-time migrations do not automatically justify permanent infrastructure.

Keeping a test, scheduling it in CI, and making it a required merge check are separate decisions. A merge requirement needs explicit agreement on necessity, reliability, cost, failure ownership, and skipped behavior. Do not silently expand branch protection when adding a job.

| Responsibility | Scope |
| --- | --- |
| Basic checks | Fast formatting, static analysis, compilation, generated-artifact consistency for relevant changes |
| Key-feature E2E | Selected real product features and their actual dependencies and hardware, following the [testing guidelines](testing.md) |
| Release automation | Build, validate, and publish the release's artifacts through existing paths |
| Notifications | Report workflow or repository activity, without implementing checks or controlling product behavior |

## Keep one reproducible execution path

Workflows own environment preparation, command invocation, diagnostics, and cleanup. Keep assertions and deployment lifecycle logic in the owning repository validation entrypoint, not long YAML shell blocks. Developers with the documented dependencies must be able to run the same operation outside the CI provider. An approved scenario needing an entrypoint belongs with its feature's validation, not in a second CI implementation.

Reuse setup and build paths. Compatible jobs evaluating the same source and dependencies may share an artifact instead of rebuilding it independently. Cache dependencies and compilation work, not successful test outcomes or stale binaries.

Run the package or image built from the change and verify that normal installation, startup, and the selected feature consume it. Source execution does not validate a wheel or image, and manual container repair does not validate the distributed image. Assert semantic resource fields in the owning validation, not counts of rendered text. Compilation, rendering, and dry runs are not E2E; missing real dependencies or hardware means execution did not occur, not a mocked or skipped pass.

## Select triggers, resources, and permissions

Choose work by affected features and dependencies. Path filters must include shared protocols, dependency manifests and locks, build and deployment configuration, and validation entrypoints—not only nearby source. When impact is uncertain, choose the broader relevant existing task rather than silently omit it.

Separate fast checks from expensive cluster, GPU, multi-node, and performance runs. Use representative combinations rather than a Cartesian product of models, hardware, topology, and parameters. Prefer on-demand execution when sufficient; periodic execution needs a specific unmet need. A run's hardware is an execution condition, not a universal user requirement.

Define concurrency and timeouts, and cancel superseded verification runs while preserving cleanup. Release publication and shared-environment operations need their own cancellation policy.

Each run owns and cleans up its mutable resources on success, failure, and cancellation. Shared runners must neither change another run's state nor delete another workload. Reuse existing identity and lifecycle mechanisms rather than adding content hashes, frozen baselines, or a resource-management framework.

Use only required permissions and credentials. Untrusted PR code must not receive publishing credentials or unrestricted access to shared GPU runners and clusters. Use a trusted execution context or isolated environment, not a privileged event to bypass fork restrictions.

## Review execution and maintenance cost

First trace correctness from event and change selection through setup, build, artifact transfer, invocation, reporting, and cleanup. Run the owning command in the intended environment, inspect outputs and cleanup, and exercise the changed CI wiring in an authorized run.

Verify artifact identity, real dependencies, event trust, timeouts, and failure and cancellation paths. Check required-check states after filtering, skipping, and cancellation: they must not misrepresent validation or remain indefinitely pending.

Report what ran, its source or artifact identity, relevant environment conditions, and outcome. Distinguish product failures, setup failures, and skipped execution. Preserve useful command output and component diagnostics without credentials, sensitive payloads, or private infrastructure details.

Do not hide failures with blanket retries, unconditional success, swallowed exit codes, or empty results. Diagnose flaky behavior; explicitly disable or isolate an unreliable check during repair instead of presenting it as a reliable pass.

Then independently review necessity and simplicity. Remove duplicate builds, copied deployment lifecycles, workflow-embedded assertions, obsolete jobs, and unused matrix combinations. Each task must have a current purpose distinct from existing checks; prefer representative feature runs over another matrix, scheduler, or gate. Preserve the separate responsibilities of release and notification workflows rather than removing them because they share the tests' directory.

## Further reading

[Dynamo's PR workflow](https://github.com/ai-dynamo/dynamo/blob/main/.github/workflows/pr.yaml) illustrates change-based selection, hardware-specific execution, and cancellation of superseded runs. [vLLM's contribution guide](https://docs.vllm.ai/en/latest/contributing/) describes selective CI under limited compute resources. Borrow the responsibility boundaries, not their infrastructure size or complete matrices.
