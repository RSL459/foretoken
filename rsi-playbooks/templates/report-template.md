# Optimization Report

English | [简体中文](report-template_zh.md)

Use this for the task's `report.md`. Summarize results first, then briefly explain the iterations. Deliver a file by default; keep the report updated on a document platform when the user specifies one.

## Results summary

Briefly state the final approach and main performance changes. Specify the model, software version, hardware, workload, and concurrency. Use separate tables for different conditions, each starting with its initial reference approach (base).

Select metrics from the task. Give each metric a measured-value column and a change-from-base column, with units and improvement direction in the heading.

| Approach | Change | Metric A (unit) | Change from base | Metric B (unit) | Change from base | Retained? |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| base | Initial approach | Measured value | 0% | Measured value | 0% | Initial reference |
| Approach name | Specific operation | Measured value | Percentage change | Measured value | Percentage change | Actual decision |

List results in iteration order, including regressions. Calculate percentage change as `(measured value / base value - 1) × 100%`. Mark unmeasured or undefined values with “—” and a brief explanation.

## Iterations

Give each iteration a short paragraph: why it was tried, what changed, what happened, and whether it was retained. Use the names from the summary table and link original results. Explain operations and effects in natural language, briefly defining necessary terms on first use.

## Final approach

Describe the retained changes, overall effect, and open questions. Link configurations, code, and figures. Briefly summarize time and resource use as required by the task; keep full commands and logs in run records.
