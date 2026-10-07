<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 维护运行时存储

[English](runtime-cache.md) | 简体中文

RuntimeCache 为 model-server 和 frontend 提供持久模型文件与引擎缓存。部署配置和自备模型目录的用法见[模型存储](../model-storage_zh.md)。

## 修改存储创建流程

RuntimeCache 控制器管理 PVC、容量和就绪状态，工作负载控制器挂载它发布的 claim。管理员指定的 `workload.cache.claimName` 优先使用，仍由外部管理。

目录存储由 CLI 解析节点可见路径，再创建与控制器 PVC 匹配的静态 PV。claim 名称、卷名称、访问模式和绑定容量统一由控制器决定，CLI 使用该结果。目录的绑定容量不代表文件系统配额。

本地 k3d 挂载和单节点目录使用 PV 节点亲和性。多节点绝对路径要求所有节点已经能在该位置访问同一共享文件系统；目录存储流程不传输文件，也不安装共享存储。

动态存储通过 StorageClass 创建。配置 `maxSize` 后，只要任一观测挂载点的空闲比例降到 20% 或以下，控制器就申请将容量翻倍，直到上限。扩容失败时，已绑定的卷仍可能可用；通过 RuntimeCache condition 和 PVC 事件区分扩容失败与绑定失败。

## 删除与重部署时保留数据

使用 `Retain` 时，删除 RuntimeCache 会由控制器解除 PVC 的归属关系。路径、绑定和归属一致的目录 claim 可由新缓存接管。删除 Namespace 仍会删除其中的 PVC。

CLI 默认保留目录 PV。旧 claim 删除后，重新部署可将同一 PV 绑定到新 PVC。更新绑定前会核对资源版本和旧 claim；属于其他部署的卷，或路径、节点位置已变化的卷，需要使用新的缓存名称。

设置 `retentionPolicy: Delete` 时，控制器申请删除 PVC，Kubernetes 等待工作负载释放它后完成删除，CLI 再删除目录 PV 对象。目录 PV 的回收策略为 `Retain`，因此文件保留；动态卷按 StorageClass 的回收策略处理。

## 修改缓存位置

自备模型放在 `models` 下，模型来源缓存保留上游布局，包括 `models/hub`。共享的 artifacts 解析器负责查找本地模型和 tokenizer 目录，对外模型标识保持不变。相对引用限制在模型根目录内，单个文件会报错；下载和格式校验由引擎及 tokenizer 加载器负责。

引擎缓存位于数据根目录下的 `vllm`、`torch` 和 `triton`。Triton 使用 `triton/<节点名>` 隔离不同节点的写入，并在同节点 Pod 重建后复用。缓存路径修改通过 Group 滚动更新生效，旧 Group 在替换前保持原环境；编译器子目录仍由引擎管理。

性能剖析结果写入同一持久数据根下的 `profiles/runs`，操作见[性能剖析指南](../../benchmarks/docs/profile/README_zh.md)。持久模型路径不拼接 namespace 或 Pod 身份。

## 排查临时缓存

启动期间持久缓存准备或写入检查失败时，单节点 model-server 会先停止失败的 EngineCore，再在 Pod 的 `/tmp` 下重试一次。多节点成员按完整 Group 重启，不独立重试。Frontend 缺少 Hub snapshot 时，可以使用临时 tokenizer 存储。

临时重试启动新引擎，不切换已运行引擎的路径，也不复制自备 checkpoint。本地模型仍从持久模型根目录读取，重试期间不可采集性能剖析结果。通过 model-server 日志和 `foretoken_runtime_cache_temporary` 确认该模式，修复持久卷后再重启工作负载。
