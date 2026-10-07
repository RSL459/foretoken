<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Testing Guidelines

English | [简体中文](testing_zh.md)

Run the existing checks and real scenarios relevant to the change. Foretoken maintains a small set of tests for key product features; a code change does not require a new test.

## Run the relevant checks

Run commands from the repository root:

| Changed area | Validation |
| --- | --- |
| Repository files and documentation | `pre-commit run --all-files` |
| Rust data plane | `make verify-data-plane` |
| Go control plane and generated artifacts | `make -C control-plane verify` |
| Python CLI | Install the package, inspect affected help, and execute the changed command against Kubernetes |
| Benchmarks | Follow the [benchmark guide](../../benchmarks/README.md) and execute the affected command or runner with its real service source |
| Helm and Kubernetes configuration | Lint and render affected modes, then execute the changed deployment path |

For Helm's baseline checks:

```bash
helm lint deploy/charts/foretoken --kube-version 1.36.3
helm template foretoken deploy/charts/foretoken --kube-version 1.36.3 > /tmp/foretoken.yaml
```

Use the relevant [k3d](../k3d-deployment.md) or [Kubernetes](../kubernetes-deployment.md) guide for deployment execution. Compilation, rendering, dry runs, and an API-server-only environment verify their own boundaries, not a working inference service. Model-quality and performance conclusions need evaluation or measurement with explicit workloads and hardware conditions, not a fixed generated sentence. Report actual commands, conditions, results, and important unexecuted checks; missing dependencies or hardware means the scenario did not run, not that it passed.

## Choose and implement a scenario

For example, a multi-model serving scenario deploys a maintained configuration through the CLI, sends requests to both models, checks their responses, and removes the deployment. It checks a user capability rather than constructing a routing table and asserting its fields. This is an example of scenario selection, not a requirement to add a test.

Start with the feature and its observable result. Read its implementation, owning documentation, and current validation, then run the relevant existing scenarios. Adapt their inputs, calls, and outcomes when supported behavior changes, preserving their purpose.

Before adding a file, case, subtest, or independent scenario—even inside an existing test—obtain explicit maintainer approval of the feature scope, coverage gap, and value of repeated execution. A feature, bug fix, refactor, or investigation does not automatically justify a persistent test; one-off validation can remain execution evidence. Do not widen public APIs or add production switches solely for testing.

Select a few representative scenarios, not a test inventory derived from functions, files, branches, parameter combinations, or every possible failure. Coverage percentages and test counts are not targets. Do not retain tests for getters, field forwarding, constant mappings, thin wrappers, private helpers, framework wiring, or upstream internals. Foretoken's real integration with upstream is in scope when it supports a selected feature.

Use real components and dependencies, preferably through the complete user path:

- Do not replace production dependencies with mocks, fake clients, stub servers, fabricated engine responses, or monkeypatched behavior. Fixtures may supply inputs and configuration or provision real resources, not implement a second component or simulator.
- Reuse the actual CLI, services, Kubernetes components, inference engine, hardware, and maintained installation, deployment, request, benchmark, and cleanup paths. Orchestration owns setup, execution, assertions, diagnostics, and teardown—not another installer, controller, or request runner.
- Focused verification must still execute the real implementation and state its narrower scope.
- Assert observable responses, applied configuration, service state, relevant metrics, and cleanup. Inspect semantic resource fields, not text counts, JSON/YAML layout, private call counts, incidental order, or complete log snapshots. Do not calculate expectations by copying the implementation under test.
- Keep related assertions together and independent features diagnosable. Name each non-trivial test by feature or behavior and precede it with a brief purpose comment.
- Isolate mutable resources, use bounded waits for observable conditions, and clean up owned resources on success, failure, and cancellation. Keep useful diagnostics without credentials or sensitive request content.

Component tests belong to their owning package, named by behavior rather than private module structure. Rust tests live in the crate's root `tests/`, not inline `src/` modules; Go and Python use standard package test locations. Cross-component E2E orchestration belongs to the feature's validation entrypoint. Do not create a generic framework or directory hierarchy for one scenario.

## Review before retaining a test

First review correctness and execution fidelity. Trace the entrypoint through real producers, consumers, and cleanup; inspect actual responses, state, and logs.

Check that the source, dependencies, and artifacts match the change, and that assertions distinguish the feature's expected outcome from a concrete wrong result—not merely startup, resource existence, or copied configuration.

Verify isolation, bounded waiting, and cleanup after failure and cancellation. For recovery features, trigger the relevant failure in the isolated real system. Historical runs or a different installation path are not current evidence.

Then independently review scope and maintenance cost. Confirm the test still serves a key feature with a current consumer and cannot be covered by another scenario without losing meaning.

Remove duplicate assertions, exhaustive matrices, incidental snapshots, unused helpers, obsolete debug scripts and fixtures, and test-only dependencies without consumers.

Keep shared preparation small and reuse the product lifecycle; ordinary refactoring without feature changes should not force test rewrites. An absent test is not itself a review finding: identify product defects separately, without automatically requiring a new permanent test.

Diagnose flaky behavior as a product, test, or environment failure. Fix or explicitly isolate it rather than adding retries or longer sleeps to obtain a pass. Remove temporary investigation code and record the actual execution outcome. Scheduling the test in CI is a separate decision under the [CI guidelines](ci.md).

## Further reading

[llm-d's contribution guide](https://github.com/llm-d/llm-d/blob/main/CONTRIBUTING.md) distinguishes component, integration, and deployed-system validation. [Kubebuilder's EnvTest reference](https://book.kubebuilder.io/reference/envtest) explains an API-server-only environment. These references clarify execution boundaries; Foretoken's feature selection and no-mock rules are defined here.
