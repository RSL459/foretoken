<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# 源码部署生命周期

[English](source-image-lifecycle.md) | 简体中文

本文说明维护源码部署功能时应保持的行为。安装、部署和并行实验的命令见[从源码部署 Foretoken](../custom-deployment_zh.md)。

## 安装与更新

`foretoken install -e .` 更新共享控制器、CRD 和默认运行环境。`foretoken deploy` 使用选定目录的源码构建，只更新本次提交的服务。

源码改动复用已有运行环境；依赖或基础镜像变化时重建环境。CLI 按 Foretoken 代码目录记住引擎目录选择。引擎源码需与选定的 Python、PyTorch 和设备库兼容。

## 构建与发布

只重建受改动影响的应用部分，并同步源码删除。完整应用发布后再更新服务；运行中的服务不依赖可写的编译缓存。

独立源码目录可以并行构建。同一源码目录内的准备和提交串行执行，平台安装、卸载与这些操作互斥。等待服务就绪时，应允许删除操作释放已占用的设备。

选定的应用和服务路由均就绪后，部署才成功。滚动更新和请求排空由控制器管理。

## 清理

保留工作负载或回滚仍需使用的应用，通过各自负责的生命周期清理闲置构建资源和发布文件。

删除候选只删除其部署，不卸载共享平台。平台卸载应在服务删除后进行，并保留模型数据。
