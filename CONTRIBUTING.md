# Contributing to Foretoken

English | [简体中文](CONTRIBUTING_zh.md)

Code, documentation, bug reports, and design discussions are welcome. All participants must follow the [Community Code of Conduct](CODE_OF_CONDUCT.md).

## Submit a change

1. Read the [code style](docs/development/code-style.md), the affected component's README, and its relevant guides. For changes requiring discussion, obtain agreement before implementation as described below.
2. Work on a short, purpose-named branch. External contributors use a fork; maintainers with write access may use one short-lived branch in the main repository per PR. Do not create bridge or refresh branches. Delete the head branch after merge or closure; other main-repository branches are reserved for explicit long-term work spanning related PRs.
3. Keep the change focused on one responsibility. Update English and Chinese documentation and maintained examples when user-visible behavior, commands, configuration, or status changes.
4. Run the [checks for the affected area](docs/development/testing.md#run-the-relevant-checks) and review the final change twice: first for correctness, then independently for simplicity and maintenance cost.
5. Open a PR with the [template](.github/PULL_REQUEST_TEMPLATE.md), keeping applicable sections. Use Draft status until it is ready for full review. Before merge, the PR must pass relevant checks and receive approval from at least one maintainer other than its author.

Use Conventional Commit-style messages that describe the actual change:

```text
feat(control-plane): add inference group reconciliation
fix(router): handle unavailable backends
docs: clarify deployment prerequisites
```

Common prefixes are `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `ci`, and `chore`; avoid vague messages such as `update` or `fix issues`.

## Discuss scope before implementation

Documentation, spelling and link fixes, reproducible bug fixes, and local cleanup without external behavior changes can be submitted directly. Tests for existing behavior do not require a design proposal, but additions still require the approval described in the [testing guidelines](docs/development/testing.md#choose-and-implement-a-scenario).

Open an issue or design proposal for changes to public interfaces (CRDs, CLI, configuration formats, or public Go/Python APIs), control-plane/data-plane protocols, components or deployment models. Also discuss new controllers, routers, autoscalers, runtime or hardware backends, external dependencies, testing methodologies, permanent CI jobs, and changes that may affect compatibility, performance results, or resource cost.

A bug report should include reproduction steps, expected and actual behavior, environment details, and minimal relevant logs.

For a major change, open an issue titled `[Proposal] ...`. Describe the problem and user scenarios, goals and non-goals, affected components, proposed interfaces or data flow, and alternatives. Include compatibility, upgrade and rollback plans, validation and observability, success criteria, dependencies, CI cost, and long-term ownership. Obtain agreement from the affected component maintainers before implementation; approval of the direction does not replace code review.

## Find the owning component

| Area | Responsibility |
| --- | --- |
| `data-plane/` | Request handling, routing, inference-engine integration, runtime data paths |
| `control-plane/` | Desired state, instance lifecycle, scaling, Kubernetes resources, recovery |
| `cli/` | Deployment submission, service status inspection, top-level command dispatch |
| `benchmarks/` | Correctness, workloads, performance, SLO evaluation, simulation |
| `deploy/` | Deployment composition, hardware configuration, release artifacts |

Tests belong to their owning package, not a repository-root `tests/` directory for module-specific behavior; see [test placement](docs/development/testing.md#choose-and-implement-a-scenario).

## Protect private information and provenance

Do not commit secrets, tokens, server addresses, private infrastructure details or kubeconfigs, model credentials, personal absolute paths, local caches, temporary outputs, or experiment data. Never send private code, credentials, server configuration, or unpublished data to external models.

Contributors are responsible for all submitted code, including AI-assisted changes. Review every changed line, verify provenance and licensing, and report only commands and validation that actually ran, with important unverified areas stated directly.

Contributions are published under [Apache License 2.0](LICENSE). Ensure you have the right to submit all included code, documentation, data, and test material.
