// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Candidate scoring and Scorer implementations.

mod composite_scorer;

use foretoken_kv_indexer::KvPrefixIndexer;

use crate::{RouteCandidate, RouteScore, RouterRequest, ScorerComposition, ScorerSignal};

// Each entry declares the module, re-exports the implementation, and binds its user-facing Scorer name.
// Scorer entries additionally declare their authoritative raw signals and composition contract.
declare_router_algorithms! {
    descriptor = ScorerDescriptor;
    least_loaded_scorer => LeastLoadedScorer = "least_loaded" {
        signals: &[ScorerSignal::OutstandingRequests],
        composition: ScorerComposition::Composable,
    },
    uniform_scorer => UniformScorer = "uniform" {
        signals: &[],
        composition: ScorerComposition::Exclusive,
    },
}

pub(crate) use composite_scorer::CompositeScorer;

/// Stable reason a scorer cannot contribute comparable values to one routing round.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ScorerUnavailableReason {
    MissingTelemetry,
    KvIndexUnavailable,
    NoApplicableSignal,
}

impl ScorerUnavailableReason {
    /// Returns the stable low-cardinality label consumed by routing metrics.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::MissingTelemetry => "missing_telemetry",
            Self::KvIndexUnavailable => "kv_index_unavailable",
            Self::NoApplicableSignal => "no_applicable_signal",
        }
    }
}

/// Complete result of evaluating one scorer for a routing round.
#[derive(Debug, Clone, PartialEq)]
pub enum RouteScorerResult {
    /// Parallel per-candidate normalized contributions. A default score marks a role to which the
    /// signal does not apply.
    Scored(Vec<RouteScore>),
    /// The signal cannot compare this round because no candidate has a usable observation.
    Unavailable(ScorerUnavailableReason),
}

impl RouteScorerResult {
    /// Returns normalized scores when the signal is available.
    pub fn scores(&self) -> Option<&[RouteScore]> {
        match self {
            Self::Scored(scores) => Some(scores),
            Self::Unavailable(_) => None,
        }
    }
}

/// Scores the complete filtered compatible, healthy physical-candidate snapshot for one round.
///
/// A scorer returns normalized atomic contributions only. Router combines multiple signals on the
/// same physical candidate and then evaluates complete executable E/P/D paths, preventing minima
/// from unrelated downstream candidates from being mixed into an impossible synthetic path.
pub trait RouteScorer<C: Send + 'static = ()>: Send + Sync {
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv_prefix_indexer: &dyn KvPrefixIndexer,
        customized_context: &mut C,
    ) -> RouteScorerResult;
}

/// Returns exact-rank Model Server outstanding requests plus frontend-local pending dispatches.
pub(crate) fn load(candidate: &RouteCandidate) -> Option<f64> {
    Some(
        candidate
            .rank_stats()?
            .running_requests
            .saturating_add(candidate.pending_requests) as f64,
    )
}

/// One candidate's observation state before normalized scoring.
pub(crate) enum CandidateSignal {
    Value(f64),
    Missing,
}

/// Produces the central least-loaded fallback from every currently observed exact-rank load.
pub(crate) fn least_loaded_result(candidates: &[RouteCandidate]) -> RouteScorerResult {
    let penalties = candidates
        .iter()
        .map(|candidate| load(candidate).map_or(CandidateSignal::Missing, CandidateSignal::Value))
        .collect();
    normalized_penalty_contributions(penalties)
        .map(RouteScorerResult::Scored)
        .unwrap_or(RouteScorerResult::Unavailable(
            ScorerUnavailableReason::MissingTelemetry,
        ))
}

/// Converts finite non-negative penalties into relative `0.0..=1.0` preferences.
///
/// Missing metrics receive `0.0`, and equal measured observations all receive `1.0`.
pub(crate) fn normalized_penalty_contributions(
    penalties: Vec<CandidateSignal>,
) -> Option<Vec<RouteScore>> {
    let values = penalties
        .iter()
        .filter_map(|penalty| match penalty {
            CandidateSignal::Value(value) => Some(*value),
            CandidateSignal::Missing => None,
        })
        .collect::<Vec<_>>();
    if values
        .iter()
        .any(|value| !value.is_finite() || *value < 0.0)
    {
        return None;
    }
    let Some(minimum) = values.iter().copied().reduce(f64::min) else {
        return None;
    };
    let maximum = values.iter().copied().reduce(f64::max)?;
    let range = maximum - minimum;
    penalties
        .into_iter()
        .map(|penalty| match penalty {
            CandidateSignal::Value(penalty) => {
                let score = if range == 0.0 {
                    1.0
                } else {
                    1.0 - (penalty - minimum) / range
                };
                RouteScore::new(score)
            }
            CandidateSignal::Missing => RouteScore::new(0.0),
        })
        .collect()
}
