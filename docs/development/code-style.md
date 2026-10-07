<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Foretoken Code Style

English | [简体中文](code-style_zh.md)

Use the [contribution guide](../../CONTRIBUTING.md) for submitting a change and the [testing guidelines](testing.md#run-the-relevant-checks) for validation commands. This page defines the design and maintenance standards that formatters cannot enforce.

These standards apply to first-party code and release artifacts. Vendored and upstream-managed sources follow their own conventions; Foretoken adapters follow this guide. New first-party source, configuration, and scripts must carry the repository SPDX notice. Mechanical formatting and generation follow the executable Makefiles, Cargo and Go tools, package configuration, and pre-commit hooks. Edit authoritative sources and regenerate derived files; every generated artifact must have an identifiable or documented source.

## Design around ownership

Trace configuration, execution, observation, decisions, and cleanup before editing one stage. Keep identities, state scopes, and lifecycle ownership consistent between producers and consumers, including when extending replicas, shards, or nodes. Choose the smallest maintainable implementation that preserves behavior and failure semantics.

Each protocol value, default, state transition, and derived calculation has one authoritative definition, consumed through a typed contract or shared helper. Each resource lifecycle has one owner for creation, use, cleanup, and publication unless an API explicitly transfers ownership. Share common execution rather than copying complete lifecycles into runners, controllers, or adapters; callers retain only their distinct inputs and policy.

Every type, helper, configuration field, check, fallback, and test needs a current responsibility. Remove it when its consumer disappears. Prefer deleting duplicate paths, reusing the existing owner, and calling mature upstream public APIs and owning paths before adding abstractions. Traits, interfaces, factories, builders, and registries need a real ownership boundary or multiple current implementations.

Keep version-sensitive and backend-specific behavior in thin adapters. Platform APIs and common control flow use inference-engine-neutral domain types. Do not build compatibility probes, fallback implementations, or plugin frameworks for unsupported versions or backends.

## Keep public interfaces deliberate

CLI flags, YAML, environment variables, CRD and API fields, status, and persistent output schemas must serve a current user choice and execution consumer. Map public fields explicitly rather than exposing entire structs or dataclasses through reflection, including in parameter sweeps.

Derive values from authoritative inputs such as model identifiers and Kubernetes resources. Internal revisions, temporary paths, controller-owned state, runtime identities, intermediate results, and orchestration context are not ordinary user configuration.

Define defaults once at their owning configuration or lifecycle boundary. Required state must not become empty strings, collections, zero values, or silent fallbacks in decoders and consumers; fail at the owning boundary. Represent absence only when it is valid domain state.

Experimental capabilities are disabled by default with explicit activation. Stable contracts must not break silently: incompatible changes require an explicit version, deprecation period, and migration path.

Keep YAML's common path short, with few required fields and precise domain names rather than broad `target`, `policy`, `owner`, `extra`, or `config` names. Advanced choices belong in a clearly owned nested block. Do not offer two fields or files for the same decision. Keep Helm values, schema, maintained examples, and documentation synchronized; examples show the smallest useful configuration, not all options.

## Expose real failures at their owner

Do not add validation, fixed limits, retries, fallbacks, hashes, baselines, or process gates by default. Prefer direct implementation, ownership, types, versions, primary keys, transactions, unique constraints, and ordinary tests. A defensive mechanism must protect a currently reachable important failure that simpler tools cannot address. Identify its triggering input or state, resource or contract owner, observable signal and user-visible result, and why the simpler mechanisms or upstream validation are insufficient.

Validate once at the owning boundary, not again downstream. Missing required state and protocol failures must remain visible rather than becoming empty results or defaults. Catch only errors the caller can handle; broad exception handling must not disguise programming errors, invalid SDK usage, or broken invariants as remote failures.

## Structure code by responsibility

Use specific domain names such as `create_client`, `metrics_url`, and `model_group`. Keep values at their narrowest owning scope; module constants need multiple consumers or a module-wide external contract, not convenience alone.

Keep related stages readable as one flow. Extract functions for meaningful stages or lifecycles, not to shorten code with fragmented forwarding helpers. Use a state-owning class in Python or a struct with methods in Go and Rust when resources, clients, configuration, or invariants persist across stages. Stateless transformations and single-stage operations remain functions; types are not namespaces or devices for shorter parameter lists or hypothetical reuse.

A state-owning module contains its lifecycle and closely related types. Current implementations' shared behavior belongs on their base class; adapter recognition, capacity, and policy remain specialized methods so each adapter is readable together. Only reusable stateless parsing, matching, and formatting move to named helper modules. Multiple classes may share a file when they share a lifecycle; do not enforce one class per file.

Split modules at independent lifecycles, protocols, backends, or ownership boundaries—not by file length. A cohesive long file can remain intact.

Entry points compose and dispatch rather than decide domain policy. Create a domain package when multiple current modules share a stable responsibility, not an empty hierarchy, generic `utils` layer, registry, or directory for future implementations.

After substantial growth, revisit the responsibility map: delete replaced paths, repeated state and stages, and forwarding layers, and ensure a split reduces the concepts and implementation maintainers must understand.

Public first-party production functions require concise doc comments explaining purpose, caller or consumer, returned or published result, and important ownership or lifecycle. Private functions owning a complete stage or unclear from their name and signature need the same context. Generated and third-party code follow their owning project.

Use a few structural comments for large blocks, multi-stage flows, non-obvious algorithms, and critical boundaries. Explain necessary ordering, resource ownership, external constraints, and state after failure or cleanup—not getters, field forwarding, constant mappings, obvious loops, or each line. Comments do not record modification history, review replies, temporary plans, or the implementer's reasoning process.

## Follow the owning language and tools

Follow surrounding code and the subtree's executable checks. Python CLI argument definitions and parsing stay separate from execution; pass explicit command types across that boundary, not `argparse.Namespace`. Benchmarks follow their existing package structure and typing style. Validate Helm and Kubernetes resources, schema, selectors, ports, namespaces, and network access as one deployment contract.

[Testing](testing.md) owns feature selection, real execution, no mocks, placement, and test review. [CI](ci.md) owns scheduling, artifact validation, permissions, cleanup, and merge-check decisions. Both reuse the product lifecycle and require current owners rather than duplicate implementations or speculative checks.

## Write documentation around the reader's task

Before adding or substantially rewriting user documentation, define the page's purpose and reader outcome, verify current code, CLI help, values, schema, maintained examples, runtime behavior and cleanup.

Read the latest guides from at least two mature projects with similar responsibilities. Compare prerequisites, first success, alternatives, verification, and troubleshooting; borrow organization, not text. Historical, deprecated, draft, and proposal material is background, not current guidance. Outline the shortest executable path before writing prose.

Give each page one responsibility. Root READMEs explain the project and one default path through setup, a successful request, and cleanup. Component READMEs describe user-visible purpose, inputs, outputs, access, and necessary limits—not source tours or private contracts. Installation, deployment, operations, troubleshooting, and reference guides own their details. Maintainer guides may explain ownership, data flow, and trade-offs while distinguishing current behavior from targets and drafts.

Commands use maintained paths, model identifiers, fields, and defaults. Explain unavoidable placeholders before use and show exact fragments for configuration changes.

Group commands only when they run sequentially, with brief comments for distinct stages; do not repeat them in an overview or narrate an obvious command.

Explain observable results, resources, and success; waiting and internal lifecycle details belong only where they affect the next action. Put alternatives at the actual decision point or link their owning guide instead of enumerating every mode up front.

When capabilities grow, revise the reader path rather than append paragraphs. State shared behavior once; place differences in focused sections and use stable entries for growing lists such as examples and contributors. Write for future users and maintainers, not the PR discussion or implementation diary.

Review the full path as a first-time user, experienced operator, and source developer. Resolve concrete friction in page responsibility, structure, and placement before editing sentences; reread adjacent steps after changes.

Independently delete duplicated commands, meta-commentary, misplaced alternatives, unnecessary implementation details, and headings without a purpose. Repeat until the default path works, choices appear where needed, and readers have no reachable blocker; then stop wording-only iteration. Formatting and tests do not replace reading.

Keep English and Chinese aligned in capability, prerequisites, commands, defaults, and limits, but write each naturally rather than translating sentence by sentence. Preserve commands, fields, types, and Kubernetes kinds readers must recognize or enter, explaining uncommon terms at first use.

## Review the final diff

Keep one responsibility per PR without unrelated refactoring, upgrades, formatting, or generated drift. Remove superseded implementations, unused configuration, duplicate defaults, obsolete documentation, and tests protecting only the old path. Confirm the base, identify a stacked PR's predecessor, and do not reintroduce behavior replaced on `main`.

Review correctness and the complete execution path first, then independently review simplicity, ownership, and maintenance cost. Follow the [contribution guide](../../CONTRIBUTING.md#protect-private-information-and-provenance) for privacy, provenance, and truthful validation reporting. Use the [PR template](../../.github/PULL_REQUEST_TEMPLATE.md) to summarize the problem, change, evidence, performance, impact, and related issue without copying these standards into the PR.
