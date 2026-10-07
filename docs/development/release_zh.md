<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 发布 Foretoken 版本

[English](release.md) | 简体中文

一次 Foretoken 发布包含 Python 包、NVIDIA 和沐曦运行环境镜像、应用压缩包及 Helm Chart。构建命令均从仓库根目录执行。

## 准备版本号

选择[发布阶段](#版本阶段)，在 `pyproject.toml` 中设置 Python 版本，在 `deploy/charts/foretoken/Chart.yaml` 的 `version` 和 `appVersion` 中设置对应的 OCI/Helm 版本。GitHub Release tag 使用带 `v` 前缀的 Python 版本。

已发布版本保持不变。再次发布时，按用途递增预发布、post-release 或 patch 序号，不覆盖已有产物。

## 构建与验证

构建机器需要 Python 3.11+、仓库 CLI 依赖、Docker BuildKit、Make、Helm，以及由 rustup 管理的 Rust 工具链。先准备兼容的 NVIDIA 和沐曦推理运行时镜像，将下面的仓库前缀和镜像引用替换为发布目的地与这两个运行时：

```bash
export REGISTRY=ghcr.io/your-org/foretoken
export INFERENCE_ENGINE_IMAGE=your-nvidia-runtime:version
export METAX_INFERENCE_ENGINE_IMAGE=your-metax-runtime:version

deploy/release-artifacts build --registry "$REGISTRY"
python -m build
```

第一条命令构建运行环境镜像，并将 `foretoken-applications-<version>-linux-amd64.tar.gz` 和 Chart 压缩包写入 `/tmp/foretoken-release`。沐曦镜像 tag 以 `-metax` 结尾。`python -m build` 需要 Python 的 `build` 包，生成的 wheel 和源码分发包位于 `dist/`。

验证 Python 分发包、应用压缩包、Chart 和受影响的镜像。NVIDIA 和沐曦运行时分别在对应设备上验证；产物构建不执行 GPU 验证。安装与请求流程见[部署指南](../../README_zh.md#快速开始)。

只导出应用压缩包、不重建运行环境时，执行：

```bash
deploy/release-artifacts export --output-dir /tmp/foretoken-release
```

## 发布产物

验证完成后，登录目标仓库并推送运行环境镜像和 Chart：

```bash
docker login ghcr.io
helm registry login ghcr.io
deploy/release-artifacts push --registry "$REGISTRY"
```

命令跳过已有 tag，可用于继续中断的发布；应用压缩包需另行上传。其他仓库与产物选择选项见 `deploy/release-artifacts --help`。

在实际构建并验证产物的提交上打 tag，以此创建 GitHub Release，并附上验证后的应用压缩包。使用[发布说明模板](release-template_zh.md)按领域说明变化、必要升级动作，并具名感谢贡献者及其提供的支持。

GitHub Release 发布后会触发 [Python 发布 workflow](../../.github/workflows/publish-python-package.yaml)，从 tag 构建并上传 PyPI。最后核对已发布的 Python 包、运行环境镜像、应用压缩包和 Chart，并使用这些产物完成一次全新安装。

## 版本阶段

Python 使用 PEP 440，OCI 镜像和 Helm 使用 SemVer。同一次发布的写法不同，但阶段和序号保持一致。

| 阶段 | 用途 | Python 版本 | OCI 与 Helm 版本 |
| --- | --- | --- | --- |
| Development | 本地或 CI 开发快照 | `0.0.1.dev1` | `0.0.1-dev.1` |
| Alpha | 早期集成与接口验证 | `0.0.1a1` | `0.0.1-alpha.1` |
| Beta | 功能完成后的兼容性与部署验证 | `0.0.1b1` | `0.0.1-beta.1` |
| Release Candidate | 正式发布前的最终验证 | `0.0.1rc1` | `0.0.1-rc.1` |
| Stable | 面向普通安装的正式版本 | `0.0.1` | `0.0.1` |
| Python post-release | 修正已发布的 Python 产物或其 metadata | `0.0.1.post1` | 通常复用 `0.0.1` |

同一阶段再次发布时递增末尾序号，例如 `0.0.1a2`；达到下一阶段的用途后再进入下一阶段。Python 的版本顺序为：

```text
0.0.1.dev1 < 0.0.1a1 < 0.0.1b1 < 0.0.1rc1 < 0.0.1 < 0.0.1.post1
```

Development 快照不创建 GitHub Release，也不上传 PyPI。OCI 镜像可用 `latest` 作为源码迭代的可变别名；它不是发布版本或 Chart 版本。

`.postN` 只修正已发布的 Python 包或 metadata，通常复用 Stable 平台产物。运行行为或平台产物变化时，发布下一 patch 版本，例如 `0.0.2`。

Alpha、Beta 和 Release Candidate 需要在 pip 中允许预发布版本，或指定精确版本：

```bash
pip install --pre foretoken
pip install foretoken==0.0.1a1
```
