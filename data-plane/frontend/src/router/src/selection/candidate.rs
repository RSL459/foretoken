// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! One routable ModelGroup candidate and its immutable routing-round observation.

use std::sync::Arc;

use foretoken_model_protocol::ModelServerRole;

use crate::{RouteTargetId, RouteTargetSet, RouteTargetStats, ScalingTarget};

/// Position in the candidate slice passed to a routing algorithm.
///
/// Filters retain positions from their input snapshot and Pickers select positions from their
/// current scored slice. Algorithms cannot manufacture or modify a candidate through this type.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct CandidateIndex(pub usize);

/// One selectable routable ModelGroup. It never represents a P-D or E-P-D combination.
#[derive(Debug, Clone, PartialEq)]
pub struct RouteCandidate {
    /// Stable route target identity used by Router and Model Server Registry.
    pub route_target_id: RouteTargetId,
    /// Control-plane scaling target that owns this route target.
    pub target: ScalingTarget,
    /// Complete capacity set attributed when this route is selected.
    pub admission_targets: RouteTargetSet,
    /// Aggregate, Prefill, Decode, or Encoder execution role.
    pub role: ModelServerRole,
    /// Model served by this route target.
    pub model: String,
    /// Route target model revision.
    pub revision: String,
    /// E/P/D route-set identity, if this routable ModelGroup participates in one.
    pub pipeline_scope_id: Option<String>,
    /// Exact data-parallel replica selected within the route target.
    pub data_parallel_rank: u32,
    /// Latest route-target observation for this routing round. Target-wide gauges are available
    /// from the first snapshot; windowed rates and latencies require retained history.
    pub route_target_stats: Option<Arc<RouteTargetStats>>,
    /// Frontend-local selections that have not completed model-server dispatch.
    pub pending_requests: u64,
    /// Estimated tokens carried by `pending_requests` using prompt plus declared maximum output.
    pub pending_tokens: u64,
}

impl RouteCandidate {
    /// Returns observations for this candidate's exact DP rank.
    pub fn rank_stats(&self) -> Option<&crate::RouteTargetRankStats> {
        self.route_target_stats
            .as_ref()?
            .by_data_parallel_rank
            .get(&self.data_parallel_rank)
    }

    /// Converts this internal scored candidate into the execution decision exposed by Router.
    pub(crate) fn decision(&self) -> crate::RouteDecision {
        crate::RouteDecision {
            route_target_id: self.route_target_id.clone(),
            admission_targets: self.admission_targets.clone(),
            role: self.role,
            model: self.model.clone(),
            revision: self.revision.clone(),
            data_parallel_rank: self.data_parallel_rank,
        }
    }
}

/// Normalized route preference in `0.0..=1.0`; larger values are preferred.
///
/// The constructor rejects non-finite and out-of-range values so Pickers can use a total order.
/// Scorers keep their source units outside this type and normalize only once before returning.
#[derive(Debug, Clone, Copy)]
pub struct RouteScore {
    value: f64,
    weight: f64,
}

impl RouteScore {
    /// Creates a comparable route score from one validated normalized preference.
    pub fn new(value: f64) -> Option<Self> {
        (value.is_finite() && (0.0..=1.0).contains(&value)).then_some(Self {
            value: if value == 0.0 { 0.0 } else { value },
            weight: 1.0,
        })
    }

    /// Returns the normalized preference consumed by composite scorers and Pickers.
    pub fn value(self) -> f64 {
        self.value
    }

    /// Reports whether this scorer signal applies to the candidate's execution role.
    pub fn is_applicable(self) -> bool {
        self.weight > 0.0
    }

    /// Applies one composite component weight without changing the normalized preference.
    pub(crate) fn scaled(self, weight: f64) -> Self {
        Self {
            value: self.value,
            weight: self.weight * weight,
        }
    }

    /// Combines two applicable contributions with their weighted arithmetic mean.
    pub(crate) fn combine(self, other: Self) -> Self {
        let weight = self.weight + other.weight;
        Self {
            value: (self.value * self.weight + other.value * other.weight) / weight,
            weight,
        }
    }
}

impl Default for RouteScore {
    /// Marks a scorer signal as not applicable to this candidate's execution role.
    fn default() -> Self {
        Self {
            value: 1.0,
            weight: 0.0,
        }
    }
}

impl Eq for RouteScore {}

impl PartialEq for RouteScore {
    fn eq(&self, other: &Self) -> bool {
        self.value == other.value
    }
}

impl PartialOrd for RouteScore {
    fn partial_cmp(&self, other: &Self) -> Option<std::cmp::Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for RouteScore {
    fn cmp(&self, other: &Self) -> std::cmp::Ordering {
        self.value.total_cmp(&other.value)
    }
}

/// Router-owned view of a candidate and the parallel score produced by a `RouteScorer`.
#[derive(Debug, Clone, PartialEq)]
pub struct ScoredCandidate {
    /// Routable ModelGroup scored in the current routing round.
    pub candidate: RouteCandidate,
    /// Normalized score assigned by the Scorer and projected over an executable path by Router.
    pub score: RouteScore,
}
