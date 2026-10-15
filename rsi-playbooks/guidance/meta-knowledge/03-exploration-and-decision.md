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

The lead, Advisors, and Workers actively formulate concrete questions from references, source code, and measurements. The lead develops and revises directions, breaks down tasks, and makes cross-direction decisions, owning environment preparation, deployment and parallel experiments. Advisors contribute independent research, alternatives, and counterexamples. Workers research, identify bottlenecks, design and implement changes, and interpret results returned by the lead without waiting for Advisor proposals.

For each investigation, state what is known, what should change, and how the next step will produce useful results. If no ready-made switch, script, or tuner exists, reuse upstream capabilities or construct a focused experiment for the question, then proceed into implementation.

## Keep digging as results emerge

Once a direction is chosen, give source analysis, experiments, and implementation sustained attention. After each improvement takes effect, measure and analyze the system again, identify new bottlenecks and design choices still open to change, and formulate the next question. Revisit areas already investigated as new results emerge, continuing within the task objectives and budget. Use intermediate results to revise understanding and refine the approach:

- A gain appears: explain why it works and under what conditions, then address the remaining costs.
- Results are inconclusive: confirm the implementation took effect, inspect the expected savings and added costs, then revise the design.
- Local speedups yield limited service gains: trace the integrated execution and investigate batching, scheduling, data placement, and effects on other stages.
- Parameter settings repeatedly produce similar results: reconsider their shared execution strategy and explore different algorithms, parallel dimensions, or ways to organize work.

Larger changes can be divided into key hypotheses, a core implementation, and full integration. Address the technical questions that most affect feasibility first, then complete execution with real requests.

## Maintain the research direction

Build on previously retained approaches and comparable results. Rerun measurements to examine specific changes in versions, workloads, or implementations. Use short experiments to answer the current question, then expand measurement when gains are uncertain or tail latency or stability needs closer examination.

For builds, downloads, deployment, evaluation, and result recording, first reuse Foretoken's existing entry points, caches, and artifacts, including [incremental source updates](../../../docs/custom-deployment.md). Learn the framework's capabilities and usage before adding temporary scripts or tools, and add them only when the existing facilities cannot meet the current experiment's needs. While waiting for results, advance source reading, design, or other independent work. Analyze results promptly when they arrive and continue experimenting.

After a group of experiments, repeated similar results, or before summarizing, reconsider whether important hotspots have been explained, whether the investigation remains confined to the same execution strategy, and which deeper approaches deserve a trial. Another agent can read the code and evidence to identify omissions, counterexamples, and new design ideas; the lead makes the overall judgment.

## Explore and exchange findings in parallel

Assign complete research questions to Workers so independent directions advance together. Provide objectives, existing findings, scope, and delivery locations while leaving room for independent thinking. Workers continue through research, design, edits, and analysis of returned results, discussing mechanisms directly with Advisors and checking evidence with Recorders. At least one Worker follows the end-to-end execution path to connect local findings with system behavior.

The lead installs the shared platform once, then follows the [parallel candidate example](../../../docs/custom-deployment.md#run-candidates-in-parallel) to prepare separate worktrees and Kubernetes namespaces. Workers edit assigned candidates and deliver the checkout, changes, and explanation. The lead synchronizes and executes each delivered version from its corresponding checkout, using `--engine-source` for candidate engine changes and reusing incremental source updates and compiler caches. Keep writable runtime caches and result directories separate; share read-only model data where suitable. The lead also updates shared controller, CRD, or platform configuration.

The lead schedules parallel builds, deployment, and measurements within actual capacity, distinguishing candidate gains from shared CPU, storage, or network contention. Keep source unchanged while a candidate runs; Workers continue independent research or develop in another worktree, or resume edits after the lead releases the checkout. The lead returns results promptly for Worker analysis and further development. Worker counts need not equal GPU experiment-group counts.

Share reusable implementations, rejected hypotheses, new constraints, and composable changes promptly. The lead combines findings and selects retained changes; Workers make assigned code-integration changes, and the lead validates the combined service and accepts the result. Advisors continue exploration and reflection, and Recorders independently review and record evidence. A delivery does not end collaboration: keep advancing within scope, and send conclusions and unresolved questions to the lead when follow-up needs a new assignment.
