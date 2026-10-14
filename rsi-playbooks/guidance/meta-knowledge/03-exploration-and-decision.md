<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# 03 | Exploration and Decision-Making

English | [简体中文](03-exploration-and-decision_zh.md)

Understand the current system and relevant knowledge, then actively choose worthwhile questions, organize research and implementation, and keep working toward real improvements under the target workload.

## Choose questions worth pursuing

Study relevant research and upstream implementations, current runtime behavior, and the results and trade-offs of previous experiments. Understand the model principles, execution mechanisms, and hardware characteristics involved. Use the task objectives to identify questions still worth investigating:

- Which costs affect the main workloads, and could addressing them yield a substantial improvement?
- What have existing approaches solved, and what limitations remain?
- Which alternative ideas merit comparison, and what knowledge or experiments are missing?
- What resources do investigation, implementation, and validation require, and how can they be organized to sustain progress?

Choose directions by their importance and potential benefit. Do not limit work to superficial tuning and easy changes because deeper work is large or difficult. Invest the research and implementation effort needed for worthwhile algorithmic, operator, or architectural innovation; use effort estimates to plan stages and collaboration.

## Turn findings into research tasks

The lead, Advisors, and Workers actively formulate concrete questions from references, source code, and measurements. The lead coordinates directions and resources and makes cross-direction decisions; Advisors contribute independent research, alternatives, and counterexamples. Each Worker owns research, analysis, design, implementation, deployment, measurement, and interpretation for its assigned question, without waiting for an Advisor proposal. A task might be to reduce Gated DeltaNet (GDN) input preparation and intermediate writeback, improve work partitioning for small-batch MoE, or investigate a new scheduling or disaggregated architecture.

For each investigation, state what is known, what should change, and how the next step will produce useful results. If no ready-made switch, script, or tuner exists, reuse upstream capabilities or construct a focused experiment for the question, then proceed into implementation.

For example, if increasing speculative steps raises the number of accepted tokens but barely changes throughput, investigate the separate costs of drafting, verification, sampling, and communication. If sampling is a shared source of overhead, examine work partitioning and data reuse, then propose and compare alternative implementations.

## Keep digging as results emerge

Once a direction is chosen, give source analysis, experiments, and implementation sustained attention. After each improvement takes effect, measure and analyze the system again, identify new bottlenecks and design choices still open to change, and formulate the next question. Revisit areas already investigated as new results emerge, continuing within the task objectives and budget. Use intermediate results to revise understanding and refine the approach:

- A gain appears: explain why it works and under what conditions, then address the remaining costs.
- Results are inconclusive: confirm the implementation took effect, inspect the expected savings and added costs, then revise the design.
- Local speedups yield limited service gains: trace the integrated execution and investigate batching, scheduling, data placement, and effects on other stages.
- Parameter settings repeatedly produce similar results: reconsider their shared execution strategy and explore different algorithms, parallel dimensions, or ways to organize work.

Larger changes can be divided into key hypotheses, a core implementation, and full integration. Address the technical questions that most affect feasibility first, then complete execution with real requests. For Attention/FFN disaggregation, for example, investigate batching requirements, activation transfer, scheduling overlap, and multi-request execution in turn, always keeping the overall objective in view.

## Maintain the research direction

Build on previously retained approaches and comparable results. Rerun measurements to examine specific changes in versions, workloads, or implementations. Use short experiments to answer the current question, then expand measurement when gains are uncertain or tail latency or stability needs closer examination.

For builds, downloads, deployment, evaluation, and result recording, first reuse Foretoken's existing entry points, caches, and artifacts, including [incremental source updates](../../../docs/custom-deployment.md). Learn the framework's capabilities and usage before adding temporary scripts or tools, and add them only when the existing facilities cannot meet the current experiment's needs. While waiting for results, advance source reading, design, or other independent work. Analyze results promptly when they arrive and continue experimenting.

After a group of experiments, repeated similar results, or before summarizing, reconsider whether important hotspots have been explained, whether the investigation remains confined to the same execution strategy, and which deeper approaches deserve a trial. Another agent can read the code and evidence to identify omissions, counterexamples, and new design ideas; the lead makes the overall judgment.

## Explore and exchange findings in parallel

Assign complete research questions to Workers so independent directions advance together. Provide objectives, existing findings, resource scope, and delivery locations while leaving room for independent thinking. Within its assignment, each Worker continues through edits, deployment, measurement, analysis, and the next design iteration, discussing mechanisms directly with Advisors and checking evidence with Recorders. At least one Worker follows the end-to-end execution path to connect local findings with system behavior.

Install the shared platform once, then follow the [parallel candidate example](../../../docs/custom-deployment.md#run-candidates-in-parallel) to give concurrent candidates separate worktrees and Kubernetes namespaces. Keep writable runtime caches and result directories separate; share read-only model data where suitable. Each Worker runs `foretoken deploy` from its own worktree and uses `--engine-source` to bind its candidate's engine checkout when changing engine code. Subsequent edits reuse that candidate's incremental source updates and compiler cache; different worktrees can build and deploy concurrently. The lead coordinates controller, CRD, or shared platform configuration changes and explicitly updates the platform.

Overlap research, implementation, builds, measurements, and analysis. While one candidate builds or waits for readiness, other Workers continue their candidates; when results arrive, the responsible Worker interprets them and starts the next iteration. Schedule concurrent measurements within actual resource capacity, distinguishing candidate gains from contention for shared CPU, storage, or network resources. Research and preparation need not occupy GPUs throughout, and Worker counts need not equal GPU experiment-group counts.

Share reusable implementations, rejected hypotheses, new constraints, and composable changes promptly. The lead combines findings across directions and coordinates code integration and cross-module issues; Workers complete assigned integration and service validation. Measure combined approaches again to understand their shared costs and actual effects. Share intermediate findings while continuing within the assignment. When the question is answered or progress needs a change of scope or resources, send the lead the conclusion, evidence, and proposed next action, retaining context for subsequent work.
