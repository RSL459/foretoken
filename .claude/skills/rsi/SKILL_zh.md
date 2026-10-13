<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 在 Claude Code 中执行 RSI

[English](SKILL.md) | 简体中文

阅读本文件所在目录下的 `../../../.agents/skills/rsi/SKILL_zh.md`，遵循共用流程与角色约定。使用交互式 Agent Team，由用户设置主 Agent 的单个 `/goal`。

创建成员前，确认当前交互会话支持原生 Team。Agent Teams 是默认关闭的实验功能；SDK 或非交互会话中的命名子 Agent 仍是普通子 Agent。不可用时，按[手册中的专用会话说明](../../../rsi-playbooks/README_zh.md#claude-code)启动。保留 harness 的默认 goal 行为；由用户处理启动和设置，不自行启动另一个 CLI 或修改共享配置。

用户在主会话中设置 `/goal <完成条件>`，把执行期间维持有效任务与工作人数、回应完成或阻塞后的新任务请求、达到任务结束条件时交付结果，都纳入同一个 goal。成员保留角色上下文并接受具体任务，无需各自设置 `/goal`。主 Agent 负责构思与反思整体方案、整合证据、协调、决策、验收和交付，分配工作，也可按需要参与执行。

成员并行使用不同 checkout 时，先创建 Git worktree，再在派工中提供绝对路径。Claude Code 的 Agent 启动调用若显式传入 `isolation`，会创建普通子 Agent 而非 teammate，因此将工作区准备与 Team 成员创建分开。

接收原生结果和消息，核对任务与实际工作人数，回应续派、重分配或明确的等待、暂停、结束决定。仅在会话提供共享 Task 工具时使用它们，否则通过消息明确派工。不虚构 goal 管理工具，也不承诺自动认领或补位；有后台工作运行时，`/goal` 可能暂缓完成判定。

恢复任务时，根据原记录和预算核对仍在运行的成员，补建缺失成员后再分配未完成工作。恢复主会话的 goal 不会自动恢复 in-process teammates。用户暂停、停止及任务截止时间优先于继续派工，由主 Agent 协调资源收尾与交付。用户可用 `/goal clear` 取消 goal；取消本身不会停止实验进程。
