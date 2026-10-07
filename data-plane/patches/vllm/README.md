<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Maintain vLLM patches

English | [简体中文](README_zh.md)

Use this directory for changes applied to Foretoken's pinned vLLM source or installed vLLM Python packages. MetaX engine-source patches have a separate [bundle](../../../deploy/inference-engines/vllm-metax/patches/vllm-030/glm-5.3/README.md).

## Update a patch

Edit the matching upstream source and regenerate the unified diff. Put shared behavior in `common/`, upstream Rust changes in `rust/`, and version-specific imports, interfaces, or insertion points in `compatibility/`. Patches for another library belong beside `vllm/` in their own directory.

Add the patch to the consuming series. `source.series` defines the pinned source stack; `version-map.yaml` selects compatibility series for installed Python versions. Several versions may share a series. Series paths are relative to this directory, and patches use `-p1` from a directory containing `vllm/`.

## Validate the consuming build

For the pinned source stack, run from the repository root:

```bash
make vllm-source
```

For installed-package changes, rebuild the model-server with the selected inference runtime using the [source deployment guide](../../../docs/custom-deployment.md). The image applies missing patches and compiles the changed Python files.

Repeat source preparation or image construction to check that an already-patched tree is accepted. Exercise the affected runtime before extending the version mapping to another upstream version.
