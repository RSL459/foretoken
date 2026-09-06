// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Engine-neutral HTTP-facing boundary and the thin vLLM EngineCore adapter.

use async_trait::async_trait;
use futures::{Stream, StreamExt};
use std::collections::BTreeMap;
use std::pin::Pin;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Instant;
use thiserror::Error;
use tokio::sync::{RwLock, mpsc};
use vllm_llm::{FinishReason, Llm};
use vllm_metrics::{EngineLabels, METRICS};

use crate::backend_telemetry::{BoundaryLatencyMetrics, read_vllm_metrics};

pub use foretoken_model_protocol::{
    CumulativeHistogram, DataParallelRankTelemetry, GenerateInput, TokenErrorCode, TokenEvent,
    TokenOutput,
};

/// Stream shape shared by production vLLM and deterministic test backends.
pub type TokenStream = Pin<Box<dyn Stream<Item = Result<TokenEvent, BackendError>> + Send>>;

/// Cumulative backend observations included in a telemetry snapshot.
#[derive(Debug, Clone, Default, PartialEq)]
pub struct BackendTelemetry {
    pub running_requests: u64,
    pub max_running_requests: u64,
    pub scheduler_running_requests: Option<u64>,
    pub scheduler_waiting_requests: Option<u64>,
    pub active_prefill_tokens: Option<u64>,
    pub by_data_parallel_rank: BTreeMap<u32, DataParallelRankTelemetry>,
    pub kv_cache_usage: Option<f64>,
    pub prompt_tokens_total: Option<u64>,
    pub generation_tokens_total: Option<u64>,
    pub ttft_seconds: CumulativeHistogram,
    pub tpot_seconds: CumulativeHistogram,
    pub e2e_seconds: CumulativeHistogram,
}

/// Backend failures classified without retaining vLLM's diagnostic text.
#[derive(Debug, Error, Clone, Copy, PartialEq, Eq)]
pub enum BackendError {
    #[error("request was rejected")]
    Rejected,
    #[error("request is invalid")]
    InvalidRequest,
    #[error("backend is unavailable")]
    Unavailable,
    #[error("backend protocol failed")]
    Protocol,
    #[error("backend request failed")]
    RequestFailed,
}

/// Backend-neutral failure to encode the active inference engine's metrics.
#[derive(Debug, Error, Clone, Copy, PartialEq, Eq)]
#[error("backend metrics rendering failed")]
pub struct MetricsError;

impl BackendError {
    /// Maps a boundary failure to the terminal token code emitted to internal stream consumers.
    ///
    /// The returned wire value carries no borrowed backend diagnostics.
    pub const fn token_error_code(self) -> TokenErrorCode {
        match self {
            Self::Unavailable => TokenErrorCode::Unavailable,
            Self::Rejected | Self::InvalidRequest | Self::Protocol => TokenErrorCode::Protocol,
            Self::RequestFailed => TokenErrorCode::RequestFailed,
        }
    }

    fn from_llm(error: vllm_llm::Error) -> Self {
        match error {
            vllm_llm::Error::EmptyPromptTokenIds { .. } => Self::InvalidRequest,
            vllm_llm::Error::EngineCoreClient(error) => Self::from_engine_client(error),
        }
    }

    fn from_engine_client(error: vllm_engine_core_client::Error) -> Self {
        use vllm_engine_core_client::Error;

        match error {
            Error::EngineCoreDead
            | Error::ClientClosed { .. }
            | Error::ControlClosed { .. }
            | Error::DispatcherClosed { .. }
            | Error::HandshakeTimeout { .. }
            | Error::InputRegistrationTimeout { .. }
            | Error::Io(_)
            | Error::RequestStreamClosed { .. }
            | Error::Transport(_)
            | Error::ZmqRuntimeTask(_) => Self::Unavailable,
            Error::Encode { .. }
            | Error::Decode { .. }
            | Error::ExtValueDecode { .. }
            | Error::UnexpectedCoordinatorOutput { .. }
            | Error::UnexpectedDispatcherOutput { .. }
            | Error::UnexpectedHandshakeIdentity { .. }
            | Error::UnexpectedHandshakeMessage { .. }
            | Error::UnsupportedAuxFrames { .. }
            | Error::UnsupportedCoordinatorEngineId { .. }
            | Error::UnsupportedExternalCoordinator
            | Error::UnsupportedField { .. }
            | Error::ValueDecode(_) => Self::Protocol,
            Error::DuplicateRequestId { .. }
            | Error::InvalidDataParallelRank { .. }
            | Error::InvalidStructuredOutputsParams { .. } => Self::Rejected,
            Error::UtilityCallClosed { .. }
            | Error::UtilityCallFailed { .. }
            | Error::UtilityResultDecode { .. }
            | Error::InconsistentUtilityResults { .. }
            | Error::Shared(_) => Self::RequestFailed,
        }
    }
}

/// Minimal inference backend operations that this group-local server needs.
#[async_trait]
pub trait Backend: Send + Sync {
    /// Starts one request for the generate handler and returns its owned terminal-event stream.
    async fn generate(&self, request: GenerateInput) -> Result<TokenStream, BackendError>;

    /// Cancels request IDs supplied by the abort handler; backend ownership remains unchanged.
    async fn abort(&self, request_ids: &[String]) -> Result<(), BackendError>;

    /// Returns a snapshot published by telemetry handlers without transferring backend ownership.
    fn telemetry(&self) -> BackendTelemetry;

    /// Renders the OpenMetrics payload published by the metrics handler as an owned response body.
    fn render_openmetrics(&self) -> Result<String, MetricsError>;
}

/// vLLM adapter that retains its public `Llm` facade rather than its wire protocol.
pub struct VllmBackend {
    llm: RwLock<Option<Llm>>,
    active_requests: Arc<Mutex<ActiveRequestState>>,
    max_running_requests: u64,
    max_running_requests_by_rank: BTreeMap<u32, u64>,
    engine_labels: Vec<EngineLabels>,
    boundary_latency: Arc<Mutex<BoundaryLatencyMetrics>>,
}

impl VllmBackend {
    /// Creates the model-server adapter and retains the provided vLLM `Llm` facade until shutdown.
    pub fn new(llm: Llm, max_running_requests_by_rank: BTreeMap<u32, u64>) -> Self {
        let client = llm.engine_core_client();
        let model_name = client.model_name().to_string();
        let engine_indices = client.engine_indices();
        let engine_labels = engine_indices
            .iter()
            .copied()
            .map(|engine| EngineLabels {
                model_name: model_name.clone(),
                engine,
            })
            .collect::<Vec<_>>();
        let max_running_requests = max_running_requests_by_rank
            .values()
            .copied()
            .try_fold(0_u64, u64::checked_add)
            .expect("EngineCore capacity was validated during startup");
        Self {
            llm: RwLock::new(Some(llm)),
            active_requests: Arc::new(Mutex::new(ActiveRequestState::default())),
            max_running_requests,
            max_running_requests_by_rank,
            engine_labels,
            boundary_latency: Arc::new(Mutex::new(BoundaryLatencyMetrics::new(engine_indices))),
        }
    }

    /// Takes and shuts down the owned vLLM `Llm` facade during model-server teardown.
    pub async fn shutdown(&self) -> Result<(), BackendError> {
        let Some(llm) = self.llm.write().await.take() else {
            return Ok(());
        };
        llm.shutdown().await.map_err(BackendError::from_llm)
    }
}

#[derive(Default)]
struct ActiveRequestState {
    requests: u64,
    active_prefill_tokens: u64,
    by_data_parallel_rank: BTreeMap<u32, ActiveRequestRankState>,
}

#[derive(Clone, Default)]
struct ActiveRequestRankState {
    requests: u64,
    total_sequence_length: u64,
    active_prefill_tokens: u64,
}

struct ActiveRequestFacts {
    data_parallel_rank: Option<u32>,
    sequence_length: u64,
}

impl ActiveRequestFacts {
    /// Extracts bounded routing facts before the request is moved into the engine facade.
    fn from_request(request: &GenerateInput) -> Self {
        let prompt_tokens = u64::try_from(request.prompt_token_ids.len()).unwrap_or(u64::MAX);
        let sequence_length =
            prompt_tokens.saturating_add(u64::from(request.sampling_params.max_tokens));
        Self {
            data_parallel_rank: request.data_parallel_rank,
            sequence_length,
        }
    }
}

struct ActiveRequestGuard {
    active_requests: Arc<Mutex<ActiveRequestState>>,
    facts: ActiveRequestFacts,
    released: AtomicBool,
}

impl ActiveRequestGuard {
    /// Adds one accepted request and the exact facts removed by this guard at stream termination.
    fn accepted(
        active_requests: Arc<Mutex<ActiveRequestState>>,
        facts: ActiveRequestFacts,
    ) -> Arc<Self> {
        {
            let mut active = active_requests
                .lock()
                .expect("active request telemetry lock poisoned");
            active.requests = active.requests.saturating_add(1);
            if let Some(data_parallel_rank) = facts.data_parallel_rank {
                let rank = active
                    .by_data_parallel_rank
                    .entry(data_parallel_rank)
                    .or_default();
                rank.requests = rank.requests.saturating_add(1);
                rank.total_sequence_length = rank
                    .total_sequence_length
                    .saturating_add(facts.sequence_length);
            }
        }
        Arc::new(Self {
            active_requests,
            facts,
            released: AtomicBool::new(false),
        })
    }

    fn release(&self) {
        if !self.released.swap(true, Ordering::AcqRel) {
            let mut active = self
                .active_requests
                .lock()
                .expect("active request telemetry lock poisoned");
            active.requests = active.requests.saturating_sub(1);
            let Some(data_parallel_rank) = self.facts.data_parallel_rank else {
                return;
            };
            let rank = active
                .by_data_parallel_rank
                .get_mut(&data_parallel_rank)
                .expect("accepted request retains its data-parallel rank telemetry");
            rank.requests = rank.requests.saturating_sub(1);
            rank.total_sequence_length = rank
                .total_sequence_length
                .saturating_sub(self.facts.sequence_length);
            let remove_rank = rank.requests == 0 && rank.active_prefill_tokens == 0;
            if remove_rank {
                active.by_data_parallel_rank.remove(&data_parallel_rank);
            }
        }
    }
}

impl Drop for ActiveRequestGuard {
    fn drop(&mut self) {
        self.release();
    }
}

struct ActivePrefillGuard {
    active_requests: Arc<Mutex<ActiveRequestState>>,
    data_parallel_rank: Option<u32>,
    prompt_tokens: u64,
    released: AtomicBool,
}

impl ActivePrefillGuard {
    /// Accounts for prompt work until the engine produces its first output token or terminates.
    fn accepted(
        active_requests: Arc<Mutex<ActiveRequestState>>,
        data_parallel_rank: Option<u32>,
        prompt_tokens: u64,
    ) -> Arc<Self> {
        {
            let mut active = active_requests
                .lock()
                .expect("active request telemetry lock poisoned");
            active.active_prefill_tokens =
                active.active_prefill_tokens.saturating_add(prompt_tokens);
            if let Some(rank) = data_parallel_rank {
                let state = active.by_data_parallel_rank.entry(rank).or_default();
                state.active_prefill_tokens =
                    state.active_prefill_tokens.saturating_add(prompt_tokens);
            }
        }
        Arc::new(Self {
            active_requests,
            data_parallel_rank,
            prompt_tokens,
            released: AtomicBool::new(false),
        })
    }

    fn release(&self) {
        if !self.released.swap(true, Ordering::AcqRel) {
            let mut active = self
                .active_requests
                .lock()
                .expect("active request telemetry lock poisoned");
            active.active_prefill_tokens = active
                .active_prefill_tokens
                .saturating_sub(self.prompt_tokens);
            let Some(rank) = self.data_parallel_rank else {
                return;
            };
            let state = active
                .by_data_parallel_rank
                .get_mut(&rank)
                .expect("accepted prefill retains its data-parallel rank telemetry");
            state.active_prefill_tokens = state
                .active_prefill_tokens
                .saturating_sub(self.prompt_tokens);
            if state.requests == 0 && state.active_prefill_tokens == 0 {
                active.by_data_parallel_rank.remove(&rank);
            }
        }
    }
}

impl Drop for ActivePrefillGuard {
    fn drop(&mut self) {
        self.release();
    }
}

/// Restore external request identity and track engine-boundary latency without consumer delay.
fn tracked_stream<S>(
    stream: S,
    request_id: String,
    started_at: Instant,
    active_requests: Arc<Mutex<ActiveRequestState>>,
    request_facts: ActiveRequestFacts,
    prompt_tokens: u64,
    boundary_latency: Arc<Mutex<BoundaryLatencyMetrics>>,
) -> TokenStream
where
    S: Stream<Item = Result<vllm_llm::GenerateOutput, vllm_llm::Error>> + Send + 'static,
{
    let data_parallel_rank = request_facts.data_parallel_rank;
    let active_request = ActiveRequestGuard::accepted(active_requests.clone(), request_facts);
    let prefill = ActivePrefillGuard::accepted(active_requests, data_parallel_rank, prompt_tokens);
    // Relay vLLM output through a bounded task so the returned HTTP stream owns cancellation while
    // the adapter records only engine-boundary latency, not downstream consumer backpressure.
    let (sender, mut receiver) = mpsc::channel(1);
    tokio::spawn(async move {
        let mut first_token_at = None;
        let mut generation_tokens = 0_u64;
        let mut response_backpressured = false;
        let mut stream = Box::pin(stream);
        loop {
            let item = tokio::select! {
                _ = sender.closed() => return,
                item = stream.next() => item,
            };
            let Some(item) = item else {
                active_request.release();
                return;
            };
            let (event, terminal) = match item {
                Ok(output) if output.finish_reason == Some(FinishReason::Error) => {
                    active_request.release();
                    (
                        Ok(TokenEvent::Error {
                            request_id: request_id.clone(),
                            code: TokenErrorCode::RequestFailed,
                        }),
                        true,
                    )
                }
                Ok(mut output) => {
                    let now = Instant::now();
                    generation_tokens += output.token_ids.len() as u64;
                    if first_token_at.is_none() && !output.token_ids.is_empty() {
                        prefill.release();
                        first_token_at = Some(now);
                        if !response_backpressured {
                            boundary_latency
                                .lock()
                                .expect("boundary latency metrics lock poisoned")
                                .observe_ttft(
                                    data_parallel_rank,
                                    now.duration_since(started_at).as_secs_f64(),
                                );
                        }
                    }
                    let finish_reason = output.finish_reason.clone();
                    let terminal = finish_reason.is_some();
                    let successful_terminal = matches!(
                        finish_reason,
                        Some(FinishReason::Stop(_))
                            | Some(FinishReason::Length)
                            | Some(FinishReason::Repetition(_))
                    );
                    if successful_terminal && !response_backpressured {
                        let mut metrics = boundary_latency
                            .lock()
                            .expect("boundary latency metrics lock poisoned");
                        metrics.observe_e2e(
                            data_parallel_rank,
                            now.duration_since(started_at).as_secs_f64(),
                        );
                        if let Some(first_token_at) = first_token_at
                            && generation_tokens > 1
                        {
                            metrics.observe_tpot(
                                data_parallel_rank,
                                now.duration_since(first_token_at).as_secs_f64()
                                    / (generation_tokens - 1) as f64,
                            );
                        }
                    }
                    if terminal {
                        active_request.release();
                    }
                    output.request_id.clone_from(&request_id);
                    (Ok(TokenEvent::Token(Box::new(output.into()))), terminal)
                }
                Err(error) => {
                    active_request.release();
                    (Err(BackendError::from_llm(error)), true)
                }
            };
            match sender.try_send(event) {
                Ok(()) => {}
                Err(mpsc::error::TrySendError::Full(event)) => {
                    response_backpressured = true;
                    if sender.send(event).await.is_err() {
                        return;
                    }
                }
                Err(mpsc::error::TrySendError::Closed(_)) => return,
            }
            if terminal {
                return;
            }
        }
    });

    Box::pin(async_stream::stream! {
        while let Some(event) = receiver.recv().await {
            yield event;
        }
    })
}

#[async_trait]
impl Backend for VllmBackend {
    async fn generate(&self, request: GenerateInput) -> Result<TokenStream, BackendError> {
        let started_at = Instant::now();
        let guard = self.llm.read().await;
        let llm = guard.as_ref().ok_or(BackendError::Unavailable)?;
        let request_id = request.request_id.clone();
        let prompt_tokens = u64::try_from(request.prompt_token_ids.len()).unwrap_or(u64::MAX);
        let request_facts = ActiveRequestFacts::from_request(&request);
        let stream = llm
            .generate(request.into())
            .await
            .map_err(BackendError::from_llm)?;
        Ok(tracked_stream(
            stream,
            request_id,
            started_at,
            self.active_requests.clone(),
            request_facts,
            prompt_tokens,
            self.boundary_latency.clone(),
        ))
    }

    async fn abort(&self, request_ids: &[String]) -> Result<(), BackendError> {
        let guard = self.llm.read().await;
        let llm = guard.as_ref().ok_or(BackendError::Unavailable)?;
        llm.abort(request_ids).await.map_err(BackendError::from_llm)
    }

    fn telemetry(&self) -> BackendTelemetry {
        let vllm = read_vllm_metrics(&self.engine_labels);
        let (running_requests, active_prefill_tokens, active_by_rank) = {
            let active = self
                .active_requests
                .lock()
                .expect("active request telemetry lock poisoned");
            (
                active.requests,
                active.active_prefill_tokens,
                active.by_data_parallel_rank.clone(),
            )
        };
        let (ttft_seconds, tpot_seconds, e2e_seconds, latency_by_rank) = self
            .boundary_latency
            .lock()
            .expect("boundary latency metrics lock poisoned")
            .snapshot();
        let by_data_parallel_rank = self
            .max_running_requests_by_rank
            .iter()
            .map(|(rank, maximum)| {
                let active = active_by_rank.get(rank);
                let vllm = vllm
                    .by_data_parallel_rank
                    .get(rank)
                    .expect("configured EngineCore rank has metric labels");
                let (ttft, tpot, e2e) = latency_by_rank
                    .get(rank)
                    .expect("configured EngineCore rank has latency accumulators")
                    .clone();
                (
                    *rank,
                    DataParallelRankTelemetry {
                        running_requests: active.map_or(0, |state| state.requests),
                        max_running_requests: *maximum,
                        scheduler_running_requests: vllm.scheduler_running_requests,
                        scheduler_waiting_requests: vllm.scheduler_waiting_requests,
                        active_prefill_tokens: active
                            .map_or(0, |state| state.active_prefill_tokens),
                        inflight_tokens: active.map_or(0, |state| state.total_sequence_length),
                        kv_cache_usage: vllm.kv_cache_usage,
                        prompt_tokens_total: vllm.prompt_tokens_total,
                        generation_tokens_total: vllm.generation_tokens_total,
                        ttft_seconds: ttft,
                        tpot_seconds: tpot,
                        e2e_seconds: e2e,
                    },
                )
            })
            .collect();

        BackendTelemetry {
            running_requests,
            max_running_requests: self.max_running_requests,
            scheduler_running_requests: vllm.scheduler_running_requests,
            scheduler_waiting_requests: vllm.scheduler_waiting_requests,
            active_prefill_tokens: Some(active_prefill_tokens),
            by_data_parallel_rank,
            kv_cache_usage: vllm.kv_cache_usage,
            prompt_tokens_total: vllm.prompt_tokens_total,
            generation_tokens_total: vllm.generation_tokens_total,
            ttft_seconds,
            tpot_seconds,
            e2e_seconds,
        }
    }

    fn render_openmetrics(&self) -> Result<String, MetricsError> {
        METRICS.render().map_err(|_| MetricsError)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // Protects active routing facts from becoming lifetime aggregates or retaining facts after
    // their final owning request terminates.
    #[test]
    fn active_request_guard_tracks_and_releases_rank_facts() {
        let state = Arc::new(Mutex::new(ActiveRequestState::default()));
        let first = ActiveRequestGuard::accepted(
            state.clone(),
            ActiveRequestFacts {
                data_parallel_rank: Some(2),
                sequence_length: 100,
            },
        );
        let second = ActiveRequestGuard::accepted(
            state.clone(),
            ActiveRequestFacts {
                data_parallel_rank: Some(2),
                sequence_length: 300,
            },
        );

        {
            let active = state.lock().unwrap();
            let rank = active.by_data_parallel_rank.get(&2).unwrap();
            assert_eq!(active.requests, 2);
            assert_eq!(rank.total_sequence_length, 400);
        }

        first.release();
        {
            let active = state.lock().unwrap();
            let rank = active.by_data_parallel_rank.get(&2).unwrap();
            assert_eq!(active.requests, 1);
            assert_eq!(rank.total_sequence_length, 300);
        }

        second.release();
        let active = state.lock().unwrap();
        assert_eq!(active.requests, 0);
        assert!(active.by_data_parallel_rank.is_empty());
    }
}
