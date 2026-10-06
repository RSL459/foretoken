<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Release Description Template

Copy the template into the GitHub Release description, replace placeholders and remove unused sections. Group changes by user-facing area and acknowledge confirmed contributions.

Fill in the published versions and copy the full image references, Chart address and asset download links. Use a GitHub Compare link between the two release tags for the full changelog.

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

| Artifact | Published version or tag | Install or access path |
| --- | --- | --- |
| Python package | [package version] | `pip install foretoken==<package-version>` |
| Control-plane environment | [image tag] | [full image reference] |
| Frontend environment | [image tag] | [full image reference] |
| NVIDIA model-server environment | [image tag] | [full image reference] |
| MetaX model-server environment | [image tag] | [full image reference] |
| Application archive | [release version] | [asset download link copied from the GitHub Release] |
| Helm Chart | [Chart version] | [OCI Chart address] |
| Examples | [release tag] | [link to the examples directory at that tag] |

## Known Limitations

- [Current limitation that changes whether or how users should install, upgrade, or operate this release.]

## Thanks

- [@contributor](URL) — [specific code, test, documentation, issue, hardware, or other support].
- Thanks to everyone who reported issues, reviewed changes, tested releases, or helped improve Foretoken.

## Full Changelog

[GitHub Compare link]
```
