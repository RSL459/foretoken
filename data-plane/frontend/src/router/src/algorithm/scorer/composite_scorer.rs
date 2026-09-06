// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Weighted composition of normalized physical-candidate scoring signals.

use std::sync::Arc;

use foretoken_kv_indexer::KvPrefixIndexer;

use super::{RouteScorer, RouteScorerResult};
use crate::{RouteCandidate, RouteScore, RouterRequest, RoutingObserver, ScorerUnavailableReason};

struct Component {
    name: String,
    scorer: Arc<dyn RouteScorer>,
    weight: f64,
}

/// Combines independent normalized scorer signals with a weighted arithmetic mean.
///
/// Each component must either provide comparable observations for its whole applicable candidate
/// set or return `Unavailable`. Unavailable components are omitted and the remaining weights are
/// renormalized; when none are available, Router owns the single fallback decision.
pub(crate) struct CompositeScorer {
    components: Vec<Component>,
    observer: Arc<dyn RoutingObserver>,
}

impl CompositeScorer {
    /// Creates the configuration-owned composite after signal overlap validation.
    pub(crate) fn configured(
        components: Vec<(String, Arc<dyn RouteScorer>, f64)>,
        observer: Arc<dyn RoutingObserver>,
    ) -> Self {
        Self {
            components: components
                .into_iter()
                .map(|(name, scorer, weight)| Component {
                    name,
                    scorer,
                    weight,
                })
                .collect(),
            observer,
        }
    }
}

impl RouteScorer for CompositeScorer {
    fn score(
        &self,
        request: &RouterRequest,
        candidates: &[RouteCandidate],
        kv: &dyn KvPrefixIndexer,
        context: &mut (),
    ) -> RouteScorerResult {
        let mut combined = vec![RouteScore::default(); candidates.len()];
        let mut available_components = 0_usize;
        for component in &self.components {
            let result = component.scorer.score(request, candidates, kv, context);
            self.observer.observe_scorer(&component.name, &result);
            let RouteScorerResult::Scored(scores) = result else {
                continue;
            };
            if scores.len() != candidates.len() {
                return RouteScorerResult::Scored(scores);
            }
            if scores.iter().all(|score| !score.is_applicable()) {
                continue;
            }
            available_components += 1;
            for (target, score) in combined.iter_mut().zip(scores) {
                if !score.is_applicable() {
                    continue;
                }
                let weighted = score.scaled(component.weight);
                *target = if target.is_applicable() {
                    target.combine(weighted)
                } else {
                    weighted
                };
            }
        }
        if available_components == 0 {
            RouteScorerResult::Unavailable(ScorerUnavailableReason::NoApplicableSignal)
        } else {
            RouteScorerResult::Scored(combined)
        }
    }
}
