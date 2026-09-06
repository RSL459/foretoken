// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Bounded routing-decision observations exported without coupling Router to one metrics backend.

use foretoken_model_protocol::ModelServerRole;

use crate::{RouteScore, RouteScorerResult};

/// Central fallback selected after configured scorer signals cannot compare a routing round.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RoutingFallback {
    LeastLoaded,
    Uniform,
}

impl RoutingFallback {
    /// Returns the stable low-cardinality label used by metrics consumers.
    pub fn as_str(self) -> &'static str {
        match self {
            Self::LeastLoaded => "least_loaded",
            Self::Uniform => "uniform",
        }
    }
}

/// Receives aggregate scorer and selection events without retaining requests or target identity.
pub trait RoutingObserver: Send + Sync {
    /// Observes one configured component evaluation before unavailable components are omitted.
    fn observe_scorer(&self, _name: &str, _result: &RouteScorerResult) {}

    /// Observes the central fallback used for one routing round.
    fn observe_fallback(&self, _fallback: RoutingFallback) {}

    /// Observes one selected execution role and final normalized path score.
    fn observe_selection(&self, _role: ModelServerRole, _score: RouteScore) {}
}

pub(crate) struct NoopRoutingObserver;

impl RoutingObserver for NoopRoutingObserver {}
