<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Publish a Foretoken release

English | [简体中文](release_zh.md)

A Foretoken release includes the Python package, NVIDIA and MetaX runtime environment images, an application archive, and a Helm Chart. Run the build commands from the repository root.

## Prepare the version

Choose a [release stage](#version-stages). Set the Python version in `pyproject.toml` and the corresponding OCI/Helm version in both `version` and `appVersion` in `deploy/charts/foretoken/Chart.yaml`. GitHub Release tags use the Python version prefixed with `v`.

Published versions are immutable. For another publication, increment the appropriate pre-release, post-release, or patch number rather than replacing existing artifacts.

## Build and validate

Use a build host with Python 3.11+, the repository's CLI dependencies, Docker BuildKit, Make, Helm, and a rustup-managed Rust toolchain. Prepare compatible NVIDIA and MetaX inference-runtime images. Replace the registry prefix and image references below with the publication destination and those runtime images:

```bash
export REGISTRY=ghcr.io/your-org/foretoken
export INFERENCE_ENGINE_IMAGE=your-nvidia-runtime:version
export METAX_INFERENCE_ENGINE_IMAGE=your-metax-runtime:version

deploy/release-artifacts build --registry "$REGISTRY"
python -m build
```

The first command builds the environment images and saves `foretoken-applications-<version>-linux-amd64.tar.gz` and the Chart package in `/tmp/foretoken-release`. MetaX image tags end in `-metax`. `python -m build` requires the Python `build` package and writes the wheel and source distribution to `dist/`.

Validate the Python distribution, application archive, Chart, and affected images. Validate the NVIDIA and MetaX runtimes on their respective devices; artifact construction does not run GPU validation. Use the [deployment guides](../../README.md#quick-start) to exercise installation and requests.

To export only the application archive without rebuilding environment images:

```bash
deploy/release-artifacts export --output-dir /tmp/foretoken-release
```

## Publish

After validation, log in to the destination registry and push the environment images and Chart:

```bash
docker login ghcr.io
helm registry login ghcr.io
deploy/release-artifacts push --registry "$REGISTRY"
```

The command skips existing tags, so it can resume an incomplete publication. It does not upload the application archive. Other destinations and component selection are described by `deploy/release-artifacts --help`.

Tag the commit used to build and validate the artifacts. Create the GitHub Release at that tag and attach the validated application archive. Use the [release description template](release-template.md) to describe changes by area, required upgrade actions, and named acknowledgements of contributors and their support.

Publishing the GitHub Release triggers the [Python publication workflow](../../.github/workflows/publish-python-package.yaml), which builds from the tag and uploads to PyPI. Verify the published package, environment images, application archive, Chart, and a clean installation from those artifacts.

## Version stages

Python uses PEP 440; OCI images and Helm use SemVer. Keep the stage and sequence number aligned across both spellings.

| Stage | Purpose | Python version | OCI and Helm version |
| --- | --- | --- | --- |
| Development | Local or CI snapshot | `0.0.1.dev1` | `0.0.1-dev.1` |
| Alpha | Early integration and interface testing | `0.0.1a1` | `0.0.1-alpha.1` |
| Beta | Feature-complete compatibility and deployment testing | `0.0.1b1` | `0.0.1-beta.1` |
| Release candidate | Final validation before a stable release | `0.0.1rc1` | `0.0.1-rc.1` |
| Stable | Release for normal installation | `0.0.1` | `0.0.1` |
| Python post-release | Correction to a published Python artifact or its metadata | `0.0.1.post1` | Normally reuse `0.0.1` |

Increment the final number for another release in the same stage, such as `0.0.1a2`. Move to the next stage when the release meets that stage's purpose. Python orders these versions as follows:

```text
0.0.1.dev1 < 0.0.1a1 < 0.0.1b1 < 0.0.1rc1 < 0.0.1 < 0.0.1.post1
```

Development snapshots are not published to GitHub Releases or PyPI. OCI images may use `latest` as a mutable alias for source iteration; it is not a release or Chart version.

A `.postN` release corrects only the published Python package or metadata and normally reuses the Stable platform artifacts. Runtime behavior or platform changes require the next patch version, such as `0.0.2`.

Alpha, Beta, and Release Candidate versions require an explicit pre-release or exact version selection in pip:

```bash
pip install --pre foretoken
pip install foretoken==0.0.1a1
```
