# Goal and Technique

English | [简体中文](guidance-template_zh.md)

Name the file and title for the goal and specific technique; measurement entries name the diagnostic goal and method. Place technical entries in the appropriate [knowledge category](../guidance/knowledge/README.md) and organize the following content around the topic.

## Observations and Motivation

Start with the observed behavior, the conditions that produce it, and its impact, such as changes in latency, throughput, memory traffic, or quality under a specific workload. Explain where the existing approach encounters a bottleneck or limitation and what should improve.

## Principles and Analysis

Explain the mechanism and its causal relationships through examples, equations, or execution steps. Identify the computation, memory traffic, communication, or waiting it saves and the costs it adds. Explain how shapes, workloads, or hardware change the trade-off, using comparisons to distinguish competing explanations.

## Design

Describe how the approach organizes computation, data, state, and coordination. Explain the important choices and trade-offs through one complete execution, showing how the parts work together and why they are arranged that way.

## Implementation

Describe available code, key interfaces, and the actual execution path. State the model, hardware, precision, version, and dependency requirements that affect use. For methods requiring training or new weights, explain how to obtain and prepare them. Preserve reusable code and run entry points.

## Impact and Results

Explain changes in performance, quality, memory, or resource cost and the conditions under which they hold. Measurements identify their source, workload, and comparison; analytical predictions state their assumptions. Attribute gains to the relevant changes and explain limiting costs, counterexamples, or failed approaches.

## References

Link original papers, implementations, and relevant experiments. Version-sensitive statements point to the corresponding paper version, release, or source location.
