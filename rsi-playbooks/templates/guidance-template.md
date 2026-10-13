# Knowledge or Experience Title

English | [简体中文](guidance-template_zh.md)

State the concrete problem this entry helps investigate. Place technical knowledge under the category that owns the mechanism in [`guidance/knowledge/`](../guidance/knowledge/README.md); research methods belong in `guidance/meta-knowledge/`. Adapt the sections below to the question rather than filling every heading mechanically.

## Problem and current approach

Describe an observable cost or failure and explain how the current approach produces it. Identify the relevant model, execution stage, and producer/consumer relationship. Use a small example before introducing detailed interfaces.

Explain what the cited upstream version already implements and what question remains. Identify whether the approach is deployed, available as a research implementation, or proposed.

## Mechanism

Follow one execution from inputs through computation, state changes, communication, and output. Explain why each important design choice reduces work or changes the trade-off. Define symbols in any cost model and distinguish estimates from measured results.

For methods requiring a draft model, calibration, distillation, or changed weights, describe their source, training or preparation, and availability. For stateful methods, explain reuse, invalidation, and recovery where they affect the idea.

## Applicable conditions and trade-offs

State the shapes, workloads, hardware, precision, versions, and quality requirements that materially affect the result. Explain added computation, memory, transfers, waiting, or preparation. Include supported counterexamples or failed attempts that change when the method is useful.

## Implementation and research questions

Link the concrete implementation or public artifact. Explain the remaining question at the correct layer: algorithm, kernel, engine, request service, or resource orchestration. Keep a research hypothesis distinct from an observed implementation gap.

## Experiments that distinguish the choices

Describe representative inputs, comparison conditions, and the observations that would support or reject the explanation. Preserve reusable input construction, code, and run entry points. Connect local numerical and timing results to the target model and service workload.

If measurements exist, state their conditions and origin. Record how far integration and validation have progressed, and what evidence is still needed. Link raw runs rather than copying their full logs into the entry.

## Sources and implementation state

Give the check date and the release, commit, paper version, or PR merge state underlying version-sensitive claims. Link the original method, available implementation, and relevant measurements.

Update this entry and its bilingual category index when new evidence changes the same question. See [recording and learning](../guidance/meta-knowledge/05-recording-and-learning.md) for preserving reusable findings and lessons from inefficient work.
