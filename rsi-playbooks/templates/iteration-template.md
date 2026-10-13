# Iteration Notes

English | [简体中文](iteration-template_zh.md)

Reference for `results/<goal>/<motivation>/iterations/<name>/notes/iteration.md`. Name the executor, assigned writer, and independent reviewer. After each perf/eval command, the executor analyzes the result and the writer incorporates that interpretation, linking supporting records under `../runs/`. Keep independent review separately attributed in the same note; it does not replace the executor's analysis. The lead accepts the record and makes the decision rather than writing it.

## Question and analysis

State the question and your analysis of its causes. Cite the code, observations, prior results, or references used in that analysis.

## Hypothesis and design

Describe the proposed improvement, why it should work, and the concrete design. Identify measurements that would support or contradict the hypothesis.

## Implementation and deployment

After implementation, describe the actual changes and link source and configuration records. Identify the deployed version and material departures from the design.

## Measurements and interpretation

Append a separate explanation under each run name: link results under `../runs/<run>/`, explain workload and sample-size choices, compare with the reference result, and state whether the hypothesis was supported. Explain failures or interruptions and their effect on the conclusion, including other possible causes of the observed differences.

## Time spent

Link measured durations and label estimates for investigation, design, implementation, deployment, evaluation, and analysis. Keep overlapping durations separate.

## Behavior and attribution review

Name the independent reviewer and record findings on benchmark-specific shortcuts, model behavior, comparison conditions, and the source of gains. Link original evidence, distinguish the review from the execution notes, and state which conclusions are supported or need further measurement.

## Decision and completion

State the main agent's decision to retain, refine, or revert changes, the resulting code and deployment state, and the next question. Note any resources still needed by the next iteration.
