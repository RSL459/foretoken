# Develop an Autoscaling Algorithm

English | [简体中文](README_zh.md)

Autoscaling algorithms recommend how many complete model replicas a Pool needs. To configure an existing algorithm, use the [autoscaling guide](../../../docs/autoscaling.md).

## Add a replica recommendation

Start with the [queue algorithm](algorithm/decision/queue.go): it converts waiting requests into a replica recommendation and holds capacity when the queue is empty but requests are still active. A decision algorithm implements `core.DecisionAlgorithm`:

```go
type DecisionAlgorithm interface {
    Name() string
    RecommendReplicas(core.ScalingSnapshot) (core.ReplicaRecommendation, error)
}
```

Use the supplied snapshot for the calculation and return a recommendation with a reason and message that explain the result in service status. Each snapshot describes one Pool; encoder, prefill, and decode Pools are evaluated separately. Replica counts refer to complete ModelGroups, not individual Pods or engine ranks.

Add the implementation and its factory descriptor to [the decision registry](algorithm/decision/registry.go). The factory receives the selected `parameters` JSON object. Set defaults in the factory, decode explicitly supported fields with `core.DecodeParameters`, and validate the algorithm's parameters there.

Rebuild and deploy the controller, then select the registered name through `ModelService.spec.autoscaling.decision.algorithm`. Algorithms are compiled into the controller.

## Change when or how capacity is adjusted

Most recommendation algorithms can use the existing `periodic` trigger and `step` adjustment. Implement a different stage only when that behavior needs to change:

- A trigger implements `core.TriggerAlgorithm`: it decides whether the observation supports evaluation and supplies `PollingInterval()` for controller scheduling. Use [periodic](algorithm/trigger/periodic.go) as the example and add its descriptor to [the trigger registry](algorithm/trigger/registry.go).
- An adjustment implements `core.AdjustmentAlgorithm`: it converts a recommendation into bounded capacity, optionally applying stabilization or rate limits. Use [step](algorithm/adjustment/step.go) as the example and add its descriptor to [the adjustment registry](algorithm/adjustment/registry.go). Its factory also receives the controller's recommendation history.

Algorithms calculate results from their inputs. The ModelService controller collects observations, schedules evaluation, applies capacity, and publishes status; those operations do not belong in an algorithm.

## Check the result

Compare the recommendation, adjustment, and applied replicas in [service status](../../../docs/autoscaling.md#inspect-capacity). A recommendation can differ from applied capacity: missing, stale, or incomplete observations hold demand-driven scaling; automatic scaling also holds during a replica transition. Hard min/max bounds still apply when observations are unavailable or a transition is in progress.

The `step` history exists only in the current controller process. Restarting the controller or changing leaders starts a new stabilization history.

Run the control-plane verification target after changing an algorithm:

```bash
make -C control-plane verify
```

Then exercise it with a model workload and inspect capacity changes and successful requests. The [multi-model example](../../../examples/multi-model-quickstart/README.md) provides an autoscaling deployment.
