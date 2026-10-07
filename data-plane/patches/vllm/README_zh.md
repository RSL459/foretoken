<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 维护 vLLM 补丁

[English](README.md) | 简体中文

本目录的补丁用于 Foretoken 固定版本的 vLLM 源码，以及已安装的 vLLM Python 包。沐曦引擎源码使用独立的[补丁包](../../../deploy/inference-engines/vllm-metax/patches/vllm-030/glm-5.3/README_zh.md)。

## 更新补丁

修改匹配的上游源码，再重新生成 unified diff。共享行为放在 `common/`，上游 Rust 改动放在 `rust/`，不同版本的导入、接口和插入位置放在 `compatibility/`。其他库的补丁放在与 `vllm/` 同级的独立目录中。

将补丁加入实际使用它的清单：`source.series` 定义固定源码的补丁顺序，`version-map.yaml` 为已安装 Python 包的版本选择兼容清单。多个版本可以共用一份清单。清单路径相对于本目录；补丁从包含 `vllm/` 的目录以 `-p1` 应用。

## 验证实际构建路径

修改固定源码的补丁后，从仓库根目录执行：

```bash
make vllm-source
```

修改已安装包的补丁后，按[源码部署指南](../../../docs/custom-deployment_zh.md)使用所选推理运行时重建 model-server。镜像构建会应用缺失补丁，并编译改动的 Python 文件。

再次执行源码准备或镜像构建，确认已打补丁的源码可复用。扩展版本映射前，在对应上游版本上实际运行受影响的功能。
