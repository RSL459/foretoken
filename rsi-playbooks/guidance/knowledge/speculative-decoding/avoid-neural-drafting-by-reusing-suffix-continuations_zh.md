<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 复用后缀续写生成候选，省去神经草稿计算

[English](avoid-neural-drafting-by-reusing-suffix-continuations.md) | 简体中文 | [推测解码](README_zh.md)

## 什么时候历史能充当 draft

代码编辑、重复 agent 回合和 rollout 经常生成已在 prompt 或此前输出中出现的续写。轻量 proposer 可以搜索这些 token 序列，而不运行第二个神经网络。要判断的是历史能否足够便宜地预测下一段输出，从而值得进行目标验证。共享前缀本身无法回答：前缀缓存省去已知输入的处理，后缀推测预测的则是未知输出。

Suffix Decoding 只用一个目标模型，没有辅助神经模型，也不需要新增训练权重。它在已索引历史中匹配当前末尾 token，用续写频率排序候选，并自适应选择深度。它不同于跳过模型层或使用 adapter 的 self-speculation；后者仍有神经计算，可能还需要架构专属训练。

原报告在 CPU 上维护先前输出的全局后缀树，以及当前 prompt/生成的逐请求树，候选结构也可以是紧凑树。vLLM 当前指南描述逐请求自适应候选数量。研究报告使用候选树，不证明部署 adapter 会把同样的树传给引擎验证器；设计树实验前，需要检查已安装 adapter 返回的布局。

## 单轮过程与正确性边界

从已提交 token 前缀出发，在当前请求及允许使用的历史索引中搜索后缀，根据深度上限、频率和路径得分选择续写。把真正提议的序列或树交给目标现有验证器。目标按正确因果历史评估，接受允许的前缀或路径，采样校正/bonus，随后只提交这些输出。索引更新应使用已提交生成，不能把被拒绝的推测文本加入历史。下轮查询也必须使用提交后的后缀。

频率是用途估计，不自动等于随机 proposal 分布。确定性选出的 token 是点质量提议，即使索引给它的频率低于一。精确逐 token 验证可用目标概率 p(token) 接受它；拒绝时从去掉该 token 的目标分布校正。如果 proposer 真按频率随机抽样，验证器才需要对应归一化的实际提议分布。把启发式频率作为确定性候选的 q 会混淆两者；详见[采样与校正](reduce-correction-cost-with-fused-rejection-sampling_zh.md)。

用未实测算例说明：历史中 `return total` 出现七次，`return None` 三次。当前 `return` 后若确定性选择 `total`，它的 q 不是 0.7。目标给 `total` 的概率若为 0.4，点质量采样以 0.4 接受；真正按频率抽样则采用不同的接受与校正计算。提议很弱时，正确验证仍应保持目标输出分布。

## 成本、条件与现状

单轮成本包含查询、候选提取、主机/设备传递、目标验证和校正。有效跨度取决于匹配长度、重复频率及匹配后标识符或语法的变化。长重复片段很有价值，早期假匹配却可能让很多目标位置白算。原报告按匹配长度调整推测规模，并用续写条件频率乘积排序路径。

没有合适训练权重、负载确实重复输出、查询相对目标一步足够便宜时，此方法值得比较。新颖文本、高熵随机采样、分支很多的历史，或 CPU 索引与同步已成为瓶颈的饱和服务，都可能不适合。历史增大可提高覆盖，同时增加内存、更新与查询尾部成本。

vLLM 提交 `6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9` 已通过 Arctic Inference 集成后缀推测。文档要求额外依赖 `arctic-inference`；`num_speculative_tokens` 是上限，不代表每个请求每轮生成那么多候选。prompt n-gram 匹配也已有实现。有效的历史作用域和深度仍取决于负载。

全局历史也是数据边界。精确目标验证保护采样分布，却不会自动授权保存另一租户生成，也不会防止诊断信息暴露历史。应使用明确允许的历史范围和已有保留控制。

## 能区分原因的实验

固定目标与采样，比较无推测、只查 prompt 的 n-gram、请求本地后缀，以及允许的跨请求后缀。构造只改一个标识符的重复代码编辑、相同开头不同结尾的重复输出，并设置非重复对照。冷、热历史分别运行；若在“冷运行”前把所有评测输出先加入索引，就改变了比较问题。

记录后缀匹配长度、查询 p50/p99、候选深度、历史内存、更新/淘汰时间、主机设备传递、验证行数和首次拒绝位置。检查取消与拒绝候选没有进入已提交输出索引。贪心一致性与随机分布比较互补；复用命中率高不等于正确或更快。

随后扫描并发和历史大小，测量 TTFT、输出间隔、完成时间、吞吐、CPU 利用率及 SLO 容量。进一步研究应判断更长历史或更长匹配是否真正提高单位总时间提交量，以及便宜的逐请求索引能否胜过更大的共享索引。

## 参考

- [Suffix Decoding 原报告](https://arxiv.org/html/2411.04975)：逐请求/全局树、续写频率和自适应扩展（2024）。
- [vLLM 固定提交指南](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/docs/features/speculative_decoding/suffix.md)：集成、依赖和最大候选长度含义。
- [Arctic Inference](https://github.com/snowflakedb/ArcticInference) 负责历史索引；返回布局与索引生命周期以安装的 adapter 版本为准。
- [vLLM 固定采样器](https://github.com/vllm-project/vllm/blob/6849ca696ac9fbecec29a8a8c47f6ee18aea1ee9/vllm/v1/sample/rejection_sampler.py)：点质量提议和残差校正。
