// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

package decision

import (
	"encoding/json"
	"fmt"
	"math"

	"github.com/shiweijiezero/foretoken/control-plane/internal/autoscaling/core"
)

const dynamoLoadName = "dynamo_load"

// DynamoLoad implements the pinned Dynamo reactive token-load policy for P/D and aggregate Pools.
// The controller supplies complete rank observations; existing adjustment and lifecycle owners apply capacity.
type DynamoLoad struct {
	mode                   string
	prefillUp, prefillDown float64
	decodeUp, decodeDown   float64
}

var dynamoLoadDescriptor = core.DecisionDescriptor{Name: dynamoLoadName, Factory: NewDynamoLoad}

// Name identifies the compiled token-load policy for configuration and status consumers.
func (DynamoLoad) Name() string { return dynamoLoadName }

// RecommendReplicas evaluates each engine separately and returns a one-Group recommendation.
// Scale-down checks redistributed demand; request draining stays with the Group controller.
func (algorithm DynamoLoad) RecommendReplicas(snapshot core.ScalingSnapshot) (core.ReplicaRecommendation, error) {
	current := snapshot.Replicas.RequestedReplicas
	if snapshot.Metrics.State != core.MetricsFresh || !snapshot.Metrics.Window.Complete || len(snapshot.Metrics.EngineLoads) == 0 {
		return recommendation(current, core.RecommendationInsufficientData, core.RecommendationReasonMetricsUnavailable, "Dynamo load requires complete fresh scheduler token observations"), nil
	}
	if snapshot.Target.Role == core.RoleEncoder {
		return recommendation(current, core.RecommendationInsufficientData, core.RecommendationReasonMetricsUnavailable, "Dynamo load does not define an encoder policy"), nil
	}
	up, down := algorithm.decodeUp, algorithm.decodeDown
	if snapshot.Target.Role == core.RolePrefill {
		up, down = algorithm.prefillUp, algorithm.prefillDown
	}
	maximum := 0.0
	allBelow := true
	for _, engine := range snapshot.Metrics.EngineLoads {
		var value float64
		if snapshot.Target.Role == core.RolePrefill {
			value = float64(engine.QueuedPrefillTokens)
			if algorithm.mode != "load" {
				value /= float64(engine.ContextLength)
			}
		} else {
			// Add in floating point so independent uint64 counts cannot overflow.
			value = float64(engine.ScheduledDecodeKVTokens) + float64(engine.QueuedDecodeKVTokens)
			if snapshot.Target.Role == core.RoleAggregate {
				value += float64(engine.QueuedPrefillTokens)
			}
			value /= float64(engine.KVCapacityTokens)
		}
		maximum = math.Max(maximum, value)
		inclusiveUp := snapshot.Target.Role == core.RolePrefill || algorithm.mode == "load"
		if value > up || inclusiveUp && value == up {
			return recommendation(increment(current), core.RecommendationAvailable, core.RecommendationReasonLoadPressure, fmt.Sprintf("Group %s DP rank %d exceeds its token-load threshold", engine.GroupUID, engine.DataParallelRank)), nil
		}
		inclusiveDown := algorithm.mode == "load" || snapshot.Target.Role == core.RolePrefill && algorithm.mode == "latency"
		allBelow = allBelow && (value < down || inclusiveDown && value == down)
	}
	// Removing one Group redistributes its demand to the remaining Groups. This mirrors
	// Dynamo's consolidation check without making accepted execution an idle-only gate.
	if current > 1 && allBelow && maximum*float64(current)/float64(current-1) < up {
		return recommendation(current-1, core.RecommendationAvailable, core.RecommendationReasonLoadBelowTarget, "all engines remain below saturation after consolidation"), nil
	}
	return recommendation(current, core.RecommendationAvailable, core.RecommendationReasonStable, "engine token load keeps current capacity"), nil
}

func increment(current int32) int32 {
	if current == math.MaxInt32 {
		return current
	}
	return current + 1
}

// NewDynamoLoad owns the fixed throughput/latency presets and explicit load-mode thresholds.
// Unknown or obsolete request-count parameters fail at this configuration boundary.
func NewDynamoLoad(parameters json.RawMessage) (core.DecisionAlgorithm, error) {
	mode := "throughput"
	var prefillUp, prefillDown *uint64
	var decodeUp, decodeDown *float64
	if err := core.DecodeParameters(parameters, map[string]any{
		"mode":                        &mode,
		"prefillScaleUpQueueTokens":   &prefillUp,
		"prefillScaleDownQueueTokens": &prefillDown,
		"decodeScaleUpKVCacheUsage":   &decodeUp,
		"decodeScaleDownKVCacheUsage": &decodeDown,
	}); err != nil {
		return nil, err
	}
	policy := DynamoLoad{mode: mode, prefillUp: 1, prefillDown: 0.1, decodeUp: 1, decodeDown: 0.6}
	switch mode {
	case "throughput", "latency":
		if prefillUp != nil || prefillDown != nil || decodeUp != nil || decodeDown != nil {
			return nil, fmt.Errorf("dynamo_load custom thresholds require mode load")
		}
		if mode == "latency" {
			policy.prefillUp, policy.prefillDown, policy.decodeUp, policy.decodeDown = 0.1, 0, 0.4, 0.1
		}
	case "load":
		if prefillUp == nil || prefillDown == nil || decodeUp == nil || decodeDown == nil {
			return nil, fmt.Errorf("dynamo_load mode load requires all four token/KV thresholds")
		}
		if *prefillUp <= *prefillDown || !(*decodeDown >= 0 && *decodeUp <= 1 && *decodeUp > *decodeDown) {
			return nil, fmt.Errorf("dynamo_load scale-up thresholds must exceed scale-down thresholds; KV ratios must be in [0, 1]")
		}
		policy.prefillUp, policy.prefillDown = float64(*prefillUp), float64(*prefillDown)
		policy.decodeUp, policy.decodeDown = *decodeUp, *decodeDown
	default:
		return nil, fmt.Errorf("dynamo_load mode must be throughput, latency, or load")
	}
	return policy, nil
}
