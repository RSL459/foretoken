<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Release Description Template

Copy the template into the GitHub Release description, replace placeholders and remove unused sections. Group changes by user-facing area and acknowledge confirmed contributions.

Replace `PYTHON_VERSION` and `PLATFORM_VERSION` with the release's [Python and platform versions](release.md#version-stages).

```markdown
## Highlights

- [User-visible capability or important behavior change.] ([#PR](URL))
- [Important reliability, performance, platform, or documentation improvement.] ([#PR](URL))

## Changes

### [Area, such as deployment or inference]

- [Capability, improvement or fix, and its effect on users.] ([#PR](URL))

## Compatibility

| Area | This release | Notes |
| --- | --- | --- |
| Python | [version range] | [runtime requirement or packaging note] |
| Kubernetes | [supported range] | [deployment limitation, if relevant] |
| NVIDIA | [supported runtime/image] | [compatibility or image note] |
| MetaX | [supported runtime/image] | [compatibility or image note] |
| API and configuration | [compatible / changed] | [field, endpoint, or protocol note] |

## Breaking Changes and Deprecations

- [Removed, renamed, or behavior-changing interface.] Use [replacement or migration action].

## Upgrade Notes

1. [Required version, image, Chart, CRD, or configuration update.]
2. [Command or migration action, if required.]
3. [Default behavior or rollback consideration, if it changes the operator's action.]

## Release Artifacts

| Artifact | Version or tag | Install or access path |
| --- | --- | --- |
| Python package | `foretoken==PYTHON_VERSION` | `pip install foretoken==PYTHON_VERSION` |
| Control-plane environment | `PLATFORM_VERSION` | `ghcr.io/shiweijiezero/foretoken/control-plane-environment:PLATFORM_VERSION` |
| Frontend environment | `PLATFORM_VERSION` | `ghcr.io/shiweijiezero/foretoken/frontend-environment:PLATFORM_VERSION` |
| NVIDIA model-server environment | `PLATFORM_VERSION` | `ghcr.io/shiweijiezero/foretoken/model-server-environment:PLATFORM_VERSION` |
| MetaX model-server environment | `PLATFORM_VERSION-metax` | `ghcr.io/shiweijiezero/foretoken/model-server-environment:PLATFORM_VERSION-metax` |
| Application archive | `PLATFORM_VERSION` | `https://github.com/shiweijiezero/foretoken/releases/download/vPYTHON_VERSION/foretoken-applications-PLATFORM_VERSION-linux-amd64.tar.gz` |
| Helm Chart | `PLATFORM_VERSION` | `oci://ghcr.io/shiweijiezero/foretoken/charts/foretoken` |
| Examples | `vPYTHON_VERSION` | [examples at the release tag](https://github.com/shiweijiezero/foretoken/tree/vPYTHON_VERSION/examples) |

## Known Limitations

- [Current limitation that changes whether or how users should install, upgrade, or operate this release.]

## Thanks

- [@contributor](URL) — [specific code, test, documentation, issue, hardware, or other support].
- Thanks to everyone who reported issues, reviewed changes, tested releases, or helped improve Foretoken.

## Full Changelog

[Compare `vPREVIOUS` to `vPYTHON_VERSION`](https://github.com/shiweijiezero/foretoken/compare/vPREVIOUS...vPYTHON_VERSION)
```
