---
name: rsi
description: Execute, resume, pause, or finish an explicitly requested Foretoken RSI optimization task. Use only when the user asks to run RSI, not for ordinary coding or discussion of RSI designs.
---

<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# RSI in Claude Code

English | [简体中文](SKILL_zh.md)

Read `${CLAUDE_SKILL_DIR}/../../../.agents/skills/rsi/SKILL.md` and follow its shared workflow and role contracts. Use an interactive Agent Team and the user's single lead `/goal`.

Before spawning members, check that the interactive session supports native Teams. Agent Teams are experimental and disabled by default; named subagents in SDK or non-interactive sessions remain ordinary subagents. If Teams are unavailable, use the dedicated-session instructions in the [playbooks](../../../rsi-playbooks/README.md#claude-code). Preserve the harness's default goal behavior; leave startup and settings changes to the user rather than launching another CLI or changing shared configuration.

The user sets `/goal <completion condition>` in the lead session. Its condition includes maintaining useful tasks and the task-specified working-agent count during execution, responding to completion, blockage, and new-task requests, and delivering the optimization results at the task's end. Keep these as parts of one goal, not separate goals for each member. Members retain role context and receive concrete assignments; they do not need individual `/goal` commands. The lead conceives and reflects on the overall approach, integrates evidence, and owns coordination, decisions, acceptance, and delivery; it distributes work across members and participates in execution when useful.

For teammates working in parallel checkouts, create the Git worktrees first and pass their absolute paths in the assignments. Claude Code treats an Agent spawn with explicit `isolation` as a subagent rather than a teammate; keep teammate spawning and checkout preparation separate.

Process native results and messages, check actual assignments and working counts, and respond with follow-up work, reallocation, or an explicit wait/pause/finish decision. Use shared Task tools only when exposed by this session; otherwise coordinate explicit assignments through messages. Do not invent goal-management tools or promise automatic task claiming or staffing. `/goal` may defer evaluation while background work is running.

On resume, recover the task from its records and original budget, check live team membership, and recreate missing teammates before assigning unfinished work. A restored lead goal does not restore in-process teammates. User pause/stop and the task deadline override further assignments; coordinate owned cleanup and delivery. The user can cancel the active goal with `/goal clear`; clearing it does not itself stop experiment processes.
