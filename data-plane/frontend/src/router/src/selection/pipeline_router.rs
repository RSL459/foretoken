// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Fixed physical route selection for Aggregate, P/D, and E/P/D route sets.

use std::collections::{BTreeMap, BTreeSet};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use foretoken_kv_indexer::{KvPrefixIndexer, NoopKvPrefixIndexer};
use foretoken_model_protocol::ModelServerRole;

use crate::algorithm::scorer::least_loaded_result;
use crate::inventory::supports_request;
use crate::route_target_stats::NoopRouteTargetStatsReader;
use crate::{
    RouteCandidate, RouteDecision, RouteError, RouteInventory, RouteScore, RouteScorerResult,
    RouteSession, RouteTargetId, RouteTargetStatsReader, Router, RouterPipeline, RouterRequest,
    RoutingFallback, ScoredCandidate,
};

/// Observation window used for every route target in one routing round.
const ROUTE_TARGET_STATS_WINDOW: Duration = Duration::from_secs(60);

type PendingDispatchKey = (RouteTargetId, u32);
type PendingDispatches = BTreeMap<PendingDispatchKey, BTreeMap<String, u64>>;

/// Router implementation that runs one Filter-Scorer-Picker pipeline per selection round.
pub struct PipelineRouter<C: Send + 'static = ()> {
    inventory: Arc<dyn RouteInventory>,
    kv_prefix_indexer: Arc<dyn KvPrefixIndexer>,
    route_target_stats_reader: Arc<dyn RouteTargetStatsReader>,
    pipeline: Arc<RouterPipeline<C>>,
    pending_dispatches: Arc<Mutex<PendingDispatches>>,
}
impl<C: Send + 'static> PipelineRouter<C> {
    /// Creates a Router with no-op KV-prefix and route-target statistics readers.
    pub fn with_pipeline(inventory: Arc<dyn RouteInventory>, pipeline: RouterPipeline<C>) -> Self {
        Self {
            inventory,
            kv_prefix_indexer: Arc::new(NoopKvPrefixIndexer),
            route_target_stats_reader: Arc::new(NoopRouteTargetStatsReader),
            pipeline: Arc::new(pipeline),
            pending_dispatches: Arc::new(Mutex::new(BTreeMap::new())),
        }
    }

    /// Replaces the KV-prefix reader used by Filter and Scorer.
    pub fn with_kv_prefix_indexer(mut self, kv_prefix_indexer: Arc<dyn KvPrefixIndexer>) -> Self {
        self.kv_prefix_indexer = kv_prefix_indexer;
        self
    }

    /// Replaces the Router-owned reader used to construct candidate observations.
    pub fn with_route_target_stats_reader(
        mut self,
        route_target_stats_reader: Arc<dyn RouteTargetStatsReader>,
    ) -> Self {
        self.route_target_stats_reader = route_target_stats_reader;
        self
    }

    // Builds the immutable, rank-expanded candidate snapshot for one selection round. Dynamic
    // health, capabilities, and aggregate telemetry are captured before algorithms observe it.
    fn candidates(
        &self,
        request: &RouterRequest,
        pending: &mut PendingDispatches,
    ) -> Vec<RouteCandidate> {
        let mut candidates = self
            .inventory
            .model_routes()
            .candidates(request)
            .into_iter()
            .filter(|route| {
                self.inventory
                    .is_route_target_healthy(&route.route_target_id)
            })
            .filter(|route| {
                supports_request(
                    &self
                        .inventory
                        .effective_capabilities(&route.route_target_id),
                    request,
                )
            })
            .flat_map(|route| {
                // Read the route-target response once with the core-owned window, then share the
                // immutable snapshot across rank candidates; rank-aware facts remain keyed inside.
                let stats = self
                    .route_target_stats_reader
                    .stats(&route.route_target_id, ROUTE_TARGET_STATS_WINDOW)
                    .map(Arc::new);
                (0..route.data_parallel_size).map(move |data_parallel_rank| RouteCandidate {
                    route_target_id: route.route_target_id.clone(),
                    target: route.target.clone(),
                    admission_targets: route.admission_targets.clone(),
                    role: route.role,
                    model: route.model.clone(),
                    revision: route.revision.clone(),
                    pipeline_scope_id: route.pipeline_scope_id.clone(),
                    data_parallel_rank,
                    route_target_stats: stats.clone(),
                    pending_requests: 0,
                    pending_tokens: 0,
                })
            })
            .collect::<Vec<_>>();
        for candidate in &mut candidates {
            let key = (
                candidate.route_target_id.clone(),
                candidate.data_parallel_rank,
            );
            let dispatch = pending.entry(key).or_default();
            candidate.pending_requests = u64::try_from(dispatch.len()).unwrap_or(u64::MAX);
            candidate.pending_tokens = dispatch.values().copied().fold(0_u64, u64::saturating_add);
        }
        candidates
    }

    // Runs the complete Filter-Scorer-Picker stage and validates extension-produced indexes.
    fn select(
        &self,
        request: &RouterRequest,
        customized_context: &mut C,
        eligible: impl Fn(&RouteCandidate, &[ScoredCandidate]) -> bool,
        error: RouteError,
    ) -> Result<RouteCandidate, RouteError> {
        // Filter receives the complete compatible, healthy snapshot. Before scoring, Router keeps
        // the selectable stage plus every physical downstream alternative needed to form its
        // executable paths; unrelated stages and scopes cannot invalidate an otherwise measurable
        // selection round.
        // Scoring and reservation form one process-local transaction. This is a short, CPU-only
        // critical section and prevents concurrent requests from all observing the same stale load.
        let mut pending = self
            .pending_dispatches
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        let candidates = self
            .candidates(request, &mut pending)
            .into_iter()
            .collect::<Vec<_>>();
        let filtered_indexes = self.pipeline.filter.filter(
            request,
            &candidates,
            self.kv_prefix_indexer.as_ref(),
            customized_context,
        );
        let mut seen_indexes = BTreeSet::new();
        let filtered = filtered_indexes
            .into_iter()
            .map(|index| {
                if !seen_indexes.insert(index) {
                    return Err(RouteError::DuplicateFilterIndex { index: index.0 });
                }
                candidates
                    .get(index.0)
                    .cloned()
                    .ok_or(RouteError::InvalidFilterIndex { index: index.0 })
            })
            .collect::<Result<Vec<_>, _>>()?;
        let topology = filtered
            .iter()
            .cloned()
            .map(|candidate| ScoredCandidate {
                candidate,
                score: RouteScore::default(),
            })
            .collect::<Vec<_>>();
        let selectable_indexes = filtered
            .iter()
            .enumerate()
            .filter_map(|(index, candidate)| eligible(candidate, &topology).then_some(index))
            .collect::<Vec<_>>();
        if selectable_indexes.is_empty() {
            return Err(error);
        }
        let mut relevant_indexes = BTreeSet::new();
        for selectable_index in selectable_indexes {
            let candidate = &filtered[selectable_index];
            relevant_indexes.insert(selectable_index);
            let Some(scope) = &candidate.pipeline_scope_id else {
                continue;
            };
            let downstream_roles: &[ModelServerRole] = match candidate.role {
                ModelServerRole::Encoder => &[ModelServerRole::Prefill, ModelServerRole::Decode],
                ModelServerRole::Prefill => &[ModelServerRole::Decode],
                ModelServerRole::Aggregate | ModelServerRole::Decode => &[],
            };
            for (index, downstream) in filtered.iter().enumerate() {
                if downstream.pipeline_scope_id.as_ref() == Some(scope)
                    && downstream_roles.contains(&downstream.role)
                {
                    relevant_indexes.insert(index);
                }
            }
        }
        let filtered = relevant_indexes
            .into_iter()
            .map(|index| filtered[index].clone())
            .collect::<Vec<_>>();
        let scorer_result = self.pipeline.scorer.score(
            request,
            &filtered,
            self.kv_prefix_indexer.as_ref(),
            customized_context,
        );
        let contributions = match scorer_result {
            RouteScorerResult::Scored(contributions) => contributions,
            RouteScorerResult::Unavailable(_) => match least_loaded_result(&filtered) {
                RouteScorerResult::Scored(contributions) => {
                    self.pipeline
                        .observer
                        .observe_fallback(RoutingFallback::LeastLoaded);
                    contributions
                }
                RouteScorerResult::Unavailable(_) => {
                    self.pipeline
                        .observer
                        .observe_fallback(RoutingFallback::Uniform);
                    vec![RouteScore::new(1.0).expect("uniform score is valid"); filtered.len()]
                }
            },
        };
        if contributions.len() != filtered.len() {
            return Err(RouteError::InvalidScorerResult {
                expected: filtered.len(),
                actual: contributions.len(),
            });
        }
        let scores = project_path_scores(&filtered, &contributions);
        let scored = filtered
            .into_iter()
            .zip(scores)
            .map(|(candidate, score)| ScoredCandidate { candidate, score })
            .collect::<Vec<_>>();
        let selectable = scored
            .iter()
            .filter(|candidate| eligible(&candidate.candidate, &scored))
            .cloned()
            .collect::<Vec<_>>();
        debug_assert!(
            !selectable.is_empty(),
            "relevance preserves selectable candidates"
        );
        let picked = self
            .pipeline
            .picker
            .pick(request, &selectable, customized_context)
            .ok_or(RouteError::EmptyPickerResult)?;
        let selected = selectable
            .get(picked.0)
            .ok_or(RouteError::InvalidPickerIndex { index: picked.0 })?;
        self.pipeline
            .observer
            .observe_selection(selected.candidate.role, selected.score);
        let key = (
            selected.candidate.route_target_id.clone(),
            selected.candidate.data_parallel_rank,
        );
        pending.entry(key).or_default().insert(
            request.request_id().to_owned(),
            request.estimated_total_tokens(),
        );
        Ok(selected.candidate.clone())
    }

    // Removes only the request-stage reservation whose dispatch has completed. Telemetry refresh
    // never clears unrelated local reservations because it cannot identify which request it saw.
    fn release_pending(&self, request_id: &str, key: &PendingDispatchKey) {
        let mut pending = self
            .pending_dispatches
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner());
        if let Some(dispatches) = pending.get_mut(key) {
            dispatches.remove(request_id);
            if dispatches.is_empty() {
                pending.remove(key);
            }
        }
    }

    fn pipeline_scope_has_encoder(&self, request: &RouterRequest, pipeline_scope_id: &str) -> bool {
        self.inventory
            .model_routes()
            .candidates(request)
            .into_iter()
            .any(|route| {
                route.role == ModelServerRole::Encoder
                    && route.pipeline_scope_id.as_deref() == Some(pipeline_scope_id)
            })
    }

    fn select_initial(
        &self,
        request: &RouterRequest,
        context: &mut C,
    ) -> Result<RouteCandidate, RouteError> {
        self.select(
            request,
            context,
            |candidate, scored| match candidate.role {
                ModelServerRole::Aggregate => true,
                ModelServerRole::Prefill => {
                    candidate
                        .pipeline_scope_id
                        .as_ref()
                        .is_some_and(|pipeline_scope_id| {
                            !self.pipeline_scope_has_encoder(request, pipeline_scope_id)
                                && scored.iter().any(|other| {
                                    other.candidate.pipeline_scope_id.as_ref()
                                        == Some(pipeline_scope_id)
                                        && other.candidate.role == ModelServerRole::Decode
                                })
                        })
                }
                ModelServerRole::Encoder => {
                    candidate
                        .pipeline_scope_id
                        .as_ref()
                        .is_some_and(|pipeline_scope_id| {
                            scored.iter().any(|other| {
                                other.candidate.pipeline_scope_id.as_ref()
                                    == Some(pipeline_scope_id)
                                    && other.candidate.role == ModelServerRole::Prefill
                            }) && scored.iter().any(|other| {
                                other.candidate.pipeline_scope_id.as_ref()
                                    == Some(pipeline_scope_id)
                                    && other.candidate.role == ModelServerRole::Decode
                            })
                        })
                }
                ModelServerRole::Decode => false,
            },
            RouteError::NoMatchingRouteTarget {
                model: request.model.clone(),
            },
        )
    }

    fn select_prefill_in_pipeline_scope(
        &self,
        request: &RouterRequest,
        context: &mut C,
        pipeline_scope_id: &str,
    ) -> Result<RouteCandidate, RouteError> {
        self.select(
            request,
            context,
            |candidate, scored| {
                candidate.role == ModelServerRole::Prefill
                    && candidate.pipeline_scope_id.as_deref() == Some(pipeline_scope_id)
                    && scored.iter().any(|other| {
                        other.candidate.role == ModelServerRole::Decode
                            && other.candidate.pipeline_scope_id.as_deref()
                                == Some(pipeline_scope_id)
                    })
            },
            RouteError::NoMatchingRouteTarget {
                model: request.model.clone(),
            },
        )
    }

    fn select_decode_in_pipeline_scope(
        &self,
        request: &RouterRequest,
        context: &mut C,
        pipeline_scope_id: &str,
    ) -> Result<RouteCandidate, RouteError> {
        self.select(
            request,
            context,
            |candidate, _| {
                candidate.role == ModelServerRole::Decode
                    && candidate.pipeline_scope_id.as_deref() == Some(pipeline_scope_id)
            },
            RouteError::NoMatchingDecode {
                model: request.model.clone(),
            },
        )
    }
}

// Projects physical-candidate contributions onto concrete executable alternatives. Components
// have already been combined per candidate, so a path can never take queue from one downstream
// target and KV pressure from another.
fn project_path_scores(
    candidates: &[RouteCandidate],
    contributions: &[RouteScore],
) -> Vec<RouteScore> {
    let prefill = candidates
        .iter()
        .enumerate()
        .filter(|(_, candidate)| candidate.role == ModelServerRole::Prefill)
        .collect::<Vec<_>>();
    let decode = candidates
        .iter()
        .enumerate()
        .filter(|(_, candidate)| candidate.role == ModelServerRole::Decode)
        .collect::<Vec<_>>();

    candidates
        .iter()
        .enumerate()
        .map(|(index, candidate)| {
            let own = [index];
            match candidate.role {
                ModelServerRole::Aggregate | ModelServerRole::Decode => {
                    path_score(own, contributions)
                }
                ModelServerRole::Prefill => decode
                    .iter()
                    .filter(|(_, downstream)| {
                        downstream.pipeline_scope_id == candidate.pipeline_scope_id
                    })
                    .map(|(decode_index, _)| path_score([index, *decode_index], contributions))
                    .max()
                    .unwrap_or_else(|| path_score(own, contributions)),
                ModelServerRole::Encoder => prefill
                    .iter()
                    .filter(|(_, downstream)| {
                        downstream.pipeline_scope_id == candidate.pipeline_scope_id
                    })
                    .flat_map(|(prefill_index, _)| {
                        decode
                            .iter()
                            .filter(|(_, downstream)| {
                                downstream.pipeline_scope_id == candidate.pipeline_scope_id
                            })
                            .map(move |(decode_index, _)| {
                                path_score([index, *prefill_index, *decode_index], contributions)
                            })
                    })
                    .max()
                    .unwrap_or_else(|| path_score(own, contributions)),
            }
        })
        .collect()
}

fn path_score(
    indexes: impl IntoIterator<Item = usize>,
    contributions: &[RouteScore],
) -> RouteScore {
    indexes
        .into_iter()
        .filter_map(|index| contributions.get(index).copied())
        .filter(|score| score.is_applicable())
        .reduce(RouteScore::combine)
        .unwrap_or_default()
}

impl PipelineRouter<()> {
    /// Creates a Router with the default pipeline and no-op data readers.
    pub fn new(inventory: Arc<dyn RouteInventory>) -> Self {
        Self::with_pipeline(
            inventory,
            crate::RouterPipelineConfig::default()
                .build()
                .expect("built-in Router pipeline configuration must be valid"),
        )
    }
}

#[derive(Clone)]
enum SessionStage {
    Initial,
    Encoder { pipeline_scope_id: String },
    Prefill { pipeline_scope_id: String },
    Complete,
}

struct Session<C: Send + 'static> {
    router: PipelineRouter<C>,
    request: RouterRequest,
    customized_context: C,
    stage: SessionStage,
    outstanding_dispatches: BTreeSet<PendingDispatchKey>,
}
impl<C: Send + 'static> RouteSession for Session<C> {
    fn select_initial(&mut self) -> Result<RouteDecision, RouteError> {
        let candidate = self
            .router
            .select_initial(&self.request, &mut self.customized_context)?;
        self.stage = match candidate.role {
            ModelServerRole::Encoder => SessionStage::Encoder {
                pipeline_scope_id: candidate
                    .pipeline_scope_id
                    .clone()
                    .expect("eligible encoder has a pipeline scope"),
            },
            ModelServerRole::Prefill => SessionStage::Prefill {
                pipeline_scope_id: candidate
                    .pipeline_scope_id
                    .clone()
                    .expect("eligible prefill has a pipeline scope"),
            },
            ModelServerRole::Aggregate => SessionStage::Complete,
            ModelServerRole::Decode => unreachable!("initial eligibility rejects Decode"),
        };
        self.outstanding_dispatches.insert((
            candidate.route_target_id.clone(),
            candidate.data_parallel_rank,
        ));
        Ok(candidate.decision())
    }

    fn select_prefill(&mut self) -> Result<RouteDecision, RouteError> {
        let SessionStage::Encoder { pipeline_scope_id } = &self.stage else {
            return Err(RouteError::PrefillBeforeEncoder);
        };
        let prefill = self.router.select_prefill_in_pipeline_scope(
            &self.request,
            &mut self.customized_context,
            pipeline_scope_id,
        )?;
        self.stage = SessionStage::Prefill {
            pipeline_scope_id: prefill
                .pipeline_scope_id
                .clone()
                .expect("eligible prefill has a pipeline scope"),
        };
        self.outstanding_dispatches
            .insert((prefill.route_target_id.clone(), prefill.data_parallel_rank));
        Ok(prefill.decision())
    }

    fn select_decode(&mut self) -> Result<RouteDecision, RouteError> {
        // Decode selection builds a fresh healthy and telemetry snapshot rather than reusing
        // candidates observed for the earlier Prefill choice.
        let SessionStage::Prefill { pipeline_scope_id } = &self.stage else {
            return Err(RouteError::DecodeBeforePrefill);
        };
        let decode = self.router.select_decode_in_pipeline_scope(
            &self.request,
            &mut self.customized_context,
            pipeline_scope_id,
        )?;
        self.stage = SessionStage::Complete;
        self.outstanding_dispatches
            .insert((decode.route_target_id.clone(), decode.data_parallel_rank));
        Ok(decode.decision())
    }

    fn dispatch_complete(&mut self, decision: &RouteDecision) {
        let key = (
            decision.route_target_id.clone(),
            decision.data_parallel_rank,
        );
        if self.outstanding_dispatches.remove(&key) {
            self.router.release_pending(self.request.request_id(), &key);
        }
    }
}

impl<C: Send + 'static> Drop for Session<C> {
    fn drop(&mut self) {
        for key in std::mem::take(&mut self.outstanding_dispatches) {
            self.router.release_pending(self.request.request_id(), &key);
        }
    }
}
impl<C: Send + 'static> Router for PipelineRouter<C> {
    fn start(&self, request: RouterRequest) -> Box<dyn RouteSession> {
        Box::new(Session {
            router: Self {
                inventory: self.inventory.clone(),
                kv_prefix_indexer: self.kv_prefix_indexer.clone(),
                route_target_stats_reader: self.route_target_stats_reader.clone(),
                pipeline: self.pipeline.clone(),
                pending_dispatches: self.pending_dispatches.clone(),
            },
            customized_context: (self.pipeline.customized_context_factory)(&request),
            request,
            stage: SessionStage::Initial,
            outstanding_dispatches: BTreeSet::new(),
        })
    }
}
