<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SPDX-FileCopyrightText: Copyright contributors to the Foretoken project -->

# KV 前缀索引

KV 前缀索引记录各个模型服务器已经保存了哪些 KV cache。Router 可以用它判断：把请求发送到某个 ModelGroup 和 DP rank 时，有多少 prompt token 能直接复用，不必重新计算。

该组件只提供 KV cache 查询结果，不负责选择路由。

## 工作方式

1. 模型服务器报告 KV block 的写入、删除和清空事件。
2. 索引分别保存每个事件源、ModelGroup 和 DP rank 的 KV block，不会混用不同模型实例的数据。
3. Router 使用目标路由、DP rank 和请求的 prompt token 查询可复用前缀。
4. 索引只返回该路由能够读取的存储位置。

查询可能返回：

- `Matches`：索引能够正常查询，其中包含匹配的 prompt token 数量和存储位置。
- `Unavailable`：当前无法完成查询，例如请求缺少 token ID，或者事件源尚未同步完成。它不表示已经确认 KV cache 未命中。

## KV block 事件

- `BlockStored`：记录新保存的 block 以及它与前一个 block 的关系。
- `BlockRemoved`：删除事件指定的 block。如果索引无法识别该 block，则不会猜测或删除其他记录。
- `AllBlocksCleared`：清空对应事件源和 DP rank 的全部记录。

每个事件源的事件都带有从零开始的连续序号。出现缺失、乱序或 epoch 变化时，索引不会把不完整的数据提供给 Router；同步恢复后才会重新提供查询结果。

## 存储位置

Foretoken 将 vLLM 的存储类型转换为以下四类：

- `GPU` 和 `DEVICE` → `Device`
- `CPU` 和 `CPU_PINNED` → `HostPinned`
- `STORAGE`、`DISK` 和 `NVME` → `Disk`
- `REMOTE`、`EXTERNAL`、`NETWORK` 和 `SHARED` → `External`

`Device` 表示当前设备可直接读取的 KV cache。`HostPinned`、`Disk` 和 `External` 需要路由具备相应的恢复或传输能力，否则不会作为可复用结果返回。

## vLLM 事件转换

model-server adapter 将 vLLM 的 KV 事件、block 标识和父子关系转换成 Foretoken 使用的统一格式。删除事件只携带 vLLM block hash，因此 adapter 会保留必要的对应关系，以便找到此前写入的 block。Foretoken 不会直接把原始 vLLM hash 与请求侧的 block 标识进行比较。
