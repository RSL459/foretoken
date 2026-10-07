<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 模型存储

[English](model-storage.md)

模型部署通过持久存储复用下载的权重和运行时缓存。快速开始已经配置好缓存，无需另建存储配置即可部署：

```bash
foretoken deploy examples/quickstart --timeout 20m
```

本地 k3d 使用 `foretoken cluster create` 挂载的仓库根目录 `data/`。其他集群会将 `cache.yaml` 中的相对目录转为初始容量 10 GiB 的动态 PVC。只有一个可调度节点时使用 `ReadWriteOnce`，多个节点时使用 `ReadWriteMany`，存储类需要支持对应的访问模式。

## 选择存储类与容量

使用动态存储时，将示例 `cache.yaml` 中的 `spec` 替换为：

```yaml
spec:
  initialSize: 10Gi
  accessMode: ReadWriteMany
```

容量应足够容纳所用模型。添加 `storageClassName` 可选择存储类；所有使用者都在同一节点时，可改用 `ReadWriteOnce`。存储驱动支持在线扩容时，添加 `maxSize` 可启用自动扩容。

若要挂载其他系统管理的 PVC，在平台 values 中设置 `workload.cache.claimName`，并在各工作负载命名空间提供该 PVC。

## 使用已有目录

将 `cache.yaml` 的 `spec.directory` 设为前端和模型 Pod 均可读写的目录。本地 k3d 的相对路径以 Kustomize 目录为基准，快速开始的 `../../data` 指向仓库根目录的 `data/`。宿主目录需要挂载到 k3d 节点中，详见 [k3d 指南](k3d-deployment_zh.md)。

远程集群使用目标节点上已存在的绝对路径；跨节点使用时，共享文件系统必须在各节点提供相同路径。Foretoken 不会上传本地目录。目录存储不填写 PVC 容量或存储类字段：

```yaml
spec:
  directory: /var/lib/foretoken/data
  accessMode: ReadWriteMany
```

在首次部署前确定存储设置。更改已绑定缓存的目录、存储类、初始容量或访问模式需要使用新的 RuntimeCache 名称；扩容使用 `maxSize`，已有文件按需另行移动或复制。加载 `data/models/` 下已有 checkpoint 的方式见[模型来源](model-sources_zh.md#使用本地模型目录)。

## 保留或删除缓存数据

目录中的文件在 `foretoken delete` 后保留。动态缓存 PVC 默认使用 `retentionPolicy: Retain`；在 `cache.yaml` 中设为 `retentionPolicy: Delete`，可随缓存一起删除声明。删除示例命名空间也会删除其中的 PVC，底层数据是否保留由卷的回收策略决定。

性能剖析结果保存在同一数据根目录的 `profiles/` 下，操作见[性能剖析指南](../benchmarks/docs/profile/README_zh.md)。

## 在节点间共享下载和已加载权重

通过 Dragonfly 共享公开模型下载时，在 `deploy/platform-values.yaml` 中保存：

```yaml
modelDistribution:
  dragonfly:
    enabled: true
```

发布版平台使用：

```bash
foretoken install --values deploy/platform-values.yaml
```

源码安装使用 `foretoken install -e . --values deploy/platform-values.yaml`，保留原有镜像仓库和引擎源码选项。重新部署模型服务后使用更新的设置。

安装会准备 Dragonfly 或复用已有 release。指定某个 release 时，在 `modelDistribution.dragonfly` 下添加 `existingRelease: {name: dragonfly, namespace: dragonfly-system}`。需要认证的模型和自定义模型下载地址仍直接从提供方下载。

NVIDIA 集群已分配 RDMA 设备时，ModelExpress 可从运行中的副本加载权重。在 Dragonfly 同级添加：

```yaml
modelDistribution:
  modelexpress:
    enabled: true
```

自动权重传输适用于使用持久缓存、数据并行度为 1、专家位置固定的远程模型。显式配置的 `load-format` 保持不变；没有兼容来源的副本从已准备的文件加载。更改任一设置后重新安装并部署服务。两项功能默认关闭，设为 `enabled: false` 可关闭对应功能。
