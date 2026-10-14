<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Mmap、固定页内存与并行 I/O

[English](mmap-pinned-parallel-io.md) | 简体中文

延迟映射、整块读取和固定页暂存解决不同问题。mmap 省去初始全文件拷贝，却可能触发很多小缺页；eager 改变访问形态和内存占用；固定页主机缓冲区支持异步设备搬运，但既不加快文件系统，也不自动产生重叠。

## 字节如何流动

lazy safetensors reader 映射文件页，在请求权重时触碰相应范围。热本地文件系统的页可能已在 RAM；网络存储上不规则张量访问则可能变成昂贵缺页和小读取。最终仍需将张量复制到设备，mmap 不是存储直接到 GPU 的搬运。

eager 先读完整 shard，再逐个提供张量，访问更顺序，但会实体化更大的 CPU state dictionary。并行读 shard 增加在途 I/O，也增加驻留主机内存。八线程不代表八倍带宽，尤其各 rank 争用同一磁盘或挂载时。

固定页暂存使用可复用缓冲区：读块、放入 pinned memory、排入 H2D，等对应拷贝完成才归还。占用约为“缓冲区数量 × 大小”。传输速率 B、阶段延迟 t 时，维持不饥饿约需 `B × t` 在途字节，这只是容量估计，不是通用默认值。固定太多内存会减少可回收 RAM，影响同机任务。

例如磁盘很快，但 pageable CPU 张量的 H2D 准备发生停顿，增加存储线程并不能消除拷贝/暂存成本。反过来，固定页缓冲区也无法救活已饱和远端文件系统。直接 GPU 存储路径只有在文件系统、驱动和 loader 真正支持时，才减少部分主机暂存。

## vLLM 当前行为

[vLLM weight utilities](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/weight_utils.py)已有 lazy、eager、prefetch safetensors 策略。prefetch 填充的是页缓存，不是 GPU 的固定页暂存；自动预取识别特定网络文件系统，并考虑可用 RAM。多线程使用单独迭代器，[DefaultModelLoader](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/default_loader.py)拒绝将其与非默认 safetensors 策略组合。

同一 utilities 已接入 fastsafetensors 和 instanttensor。instanttensor 使用具有独立所有权的副本，避免 loader 复用内部存储后已返回张量失效；fastsafetensors 可使用 GDS，也有不使用 GDS 的路径。

[RunAI loader](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/model_executor/model_loader/runai_streamer_loader.py)把并发与内存上限交给外部 streamer。[ServerlessLLM 原方法](https://arxiv.org/html/2401.14351v1)解释了对齐分块、固定页池与多层流水的动机。Dynamo KVBM、LMCache 固定页缓存层是相关内存竞争者，并非权重 loader 替代品；Mooncake 注册同样对主机内存寿命提出约束。

## 定位瓶颈的实验

同一检查点放在本地和网络存储，对照冷热页缓存、lazy/eager/prefetch，以及允许的多线程和专用 loader。记录实际存储字节、major/minor faults、RSS、固定页字节、H2D 占用、逐 rank 加载时间和聚合存储吞吐。eager 只改善冷网络读取，支持“访问形态”解释；热加载几乎没有 I/O 却仍慢，应检查安装和设备传输。

另在实际暴露选项的 loader 中扫描缓冲区大小和在途数量，不编造参数。缓冲区必须按完成顺序复用，并核对模型输出。并发增加只提高 RSS、不提高吞吐，说明缓冲过量。

服务侧同时启动多个 worker，测就绪、首请求及对已有服务的影响。剩余空间是共享压力下的有界缓冲和存储/主机/设备重叠。

[模型加载与存储](README_zh.md)
