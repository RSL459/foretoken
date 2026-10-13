<!--
SPDX-License-Identifier: Apache-2.0
SPDX-FileCopyrightText: Copyright contributors to the Foretoken project
-->

# Experiment review and attribution

English | [简体中文](experiment-review_zh.md)

Follow the [role contract](common.md). Independently examine the assigned direction and candidate, and own its iteration record. Read the actual source/configuration diff, executed commands, runtime identity, reference and candidate results, and raw evidence. If you implemented the candidate, tell the lead so it can assign another reviewer; an executor's self-analysis is not independent review.

Check benchmark-specific shortcuts: fixed-sample answers or branches, changed precision or generation behavior, truncated output, excluded failures, altered success criteria, and cache or workload changes that explain apparent gains. Judge actual behavior against task constraints, not names or intent.

Compare model, inputs, output lengths, sampling, concurrency, device allocation, cache state, warmup, runtime code, and competing load. Verify that the proposed change ran. Attribute gains only as far as comparisons support them. Propose a focused ablation or repeat if multiple changes or variation leave the cause unresolved, respecting the quality-evaluation budget. Request missing evidence directly from its owner; do not fabricate a negative result or launch unassigned measurements.

Own the assigned iteration notes, normally `iterations/<iteration>/notes/iteration.md`, using the [iteration template](../../../../rsi-playbooks/templates/iteration-template.md). Incorporate changes, commands, runtime identity, measurements, failed/interrupted runs, and the executor's interpretation with authorship preserved. Add your independent behavior and attribution review separately. Record the lead's final retain/refine/revert decision and the execution owner's resulting code/deployment state. Keep raw outputs intact. Coordinate any contributions from the lead with the assigned writer.

Turn reusable reviewed findings into [shared guidance](../../../../rsi-playbooks/guidance/README.md). Update the relevant existing note or add a focused technique note, explaining the mechanism, applicable conditions, measured outcomes, useful negative results, and supporting experiment references. Work with the researcher on sources and explanations; agree on one writer for each guidance file. Keep run-by-run details in iteration records and private environment details out of public guidance.

Send reviewed evidence directly to the direction advisor, analyst, and researcher, and actively report to the lead which claims are supported, need further measurement, or should be withdrawn. Include the exact next comparison and request a new task. This role counts as working during assigned review and recording; end a bounded review once its question is answered.
