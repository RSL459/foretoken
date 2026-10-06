<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# Release 描述模板

将模板复制到 GitHub Release 描述中，替换占位内容并删除不适用的章节。按用户关心的领域归纳变更，根据已确认的贡献记录致谢。

将 `PYTHON_VERSION` 和 `PLATFORM_VERSION` 分别替换为本次发布的 [Python 版本和平台版本](release_zh.md#版本阶段)。

```markdown
## 主要亮点

- [面向用户的新能力或重要行为变化。] ([#PR](URL))
- [重要的可靠性、性能、平台或文档改进。] ([#PR](URL))

## 变更内容

### [领域，例如部署或推理]

- [新增能力、改进或修复，以及对用户的影响。] ([#PR](URL))

## 兼容性

| 范围 | 本版本 | 说明 |
| --- | --- | --- |
| Python | [版本范围] | [运行时要求或打包说明] |
| Kubernetes | [支持范围] | [相关部署限制] |
| NVIDIA | [支持的运行时/镜像] | [兼容性或镜像说明] |
| 沐曦 | [支持的运行时/镜像] | [兼容性或镜像说明] |
| API 与配置 | [兼容 / 已变化] | [字段、接口或协议说明] |

## 破坏性变更与弃用

- [删除、重命名或改变行为的接口。] 请改用[替代方式或迁移动作]。

## 升级说明

1. [需要更新的版本、镜像、Chart、CRD 或配置。]
2. [需要执行的命令或迁移动作。]
3. [默认行为或回滚方式发生变化时，说明运维者需要采取的动作。]

## 发布产物

| 产物 | 版本或 tag | 安装或访问方式 |
| --- | --- | --- |
| Python package | `foretoken==PYTHON_VERSION` | `pip install foretoken==PYTHON_VERSION` |
| 控制面运行环境 | `PLATFORM_VERSION` | `ghcr.io/shiweijiezero/foretoken/control-plane-environment:PLATFORM_VERSION` |
| 前端运行环境 | `PLATFORM_VERSION` | `ghcr.io/shiweijiezero/foretoken/frontend-environment:PLATFORM_VERSION` |
| NVIDIA 模型服务运行环境 | `PLATFORM_VERSION` | `ghcr.io/shiweijiezero/foretoken/model-server-environment:PLATFORM_VERSION` |
| 沐曦模型服务运行环境 | `PLATFORM_VERSION-metax` | `ghcr.io/shiweijiezero/foretoken/model-server-environment:PLATFORM_VERSION-metax` |
| 应用压缩包 | `PLATFORM_VERSION` | `https://github.com/shiweijiezero/foretoken/releases/download/vPYTHON_VERSION/foretoken-applications-PLATFORM_VERSION-linux-amd64.tar.gz` |
| Helm Chart | `PLATFORM_VERSION` | `oci://ghcr.io/shiweijiezero/foretoken/charts/foretoken` |
| 示例 | `vPYTHON_VERSION` | [Release tag 中的 examples](https://github.com/shiweijiezero/foretoken/tree/vPYTHON_VERSION/examples) |

## 已知限制

- [会影响本版本安装、升级或使用方式的当前限制。]

## 致谢

- [@contributor](URL) — [具体说明代码、测试、文档、问题定位、硬件或其他支持内容]。
- 感谢所有提交问题、评审变更、验证版本或帮助改进 Foretoken 的贡献者。

## 完整变更记录

[比较 `vPREVIOUS` 与 `vPYTHON_VERSION`](https://github.com/shiweijiezero/foretoken/compare/vPREVIOUS...vPYTHON_VERSION)
```
