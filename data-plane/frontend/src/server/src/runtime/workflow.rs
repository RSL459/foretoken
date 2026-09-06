// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Executes aggregate, P/D, and E/P/D generation while retaining cross-stage cleanup ownership.

use foretoken_llm_facade::{
    LlmFacadeResolver, MultiStageCleanup, RouteStage, TokenStream, abort_on_drop, consume_encoder,
    consume_prefill, encoder_stage_request, inject_ec_transfer_params, pd_stage_requests,
};
use foretoken_model_protocol::ModelServerRole;
use foretoken_router::{RouteDecision, RouteError};

use super::GenerationError;

/// Executes the route-selected generation workflow and returns its client-visible stream.
///
/// Runtime dispatch calls this once after initial routing. It owns intermediate stages until the
/// final stream takes cleanup ownership, or returns a pre-stream error for the HTTP adapter.
pub(crate) async fn execute_workflow(
    resolver: &dyn LlmFacadeResolver,
    session: &mut dyn foretoken_router::RouteSession,
    initial: RouteDecision,
    request: vllm_llm::GenerateRequest,
) -> Result<(RouteDecision, TokenStream), GenerationError> {
    // The router chooses only the initial stage. Encoder output prepares prefill transfer state,
    // and decode is selected only after prefill completes within the same routing session.
    match initial.role {
        ModelServerRole::Aggregate => execute_aggregate(resolver, session, initial, request).await,
        ModelServerRole::Prefill => {
            execute_pd(
                resolver,
                session,
                initial,
                request,
                None,
                MultiStageCleanup::new(),
            )
            .await
        }
        ModelServerRole::Encoder => {
            let (descriptor, cleanup) =
                execute_encoder(resolver, session, initial, request.clone()).await?;
            let prefill = session.select_prefill().map_err(unavailable)?;
            execute_pd(
                resolver,
                session,
                prefill,
                request,
                Some(descriptor),
                cleanup,
            )
            .await
        }
        ModelServerRole::Decode => Err(GenerationError::Internal),
    }
}

fn unavailable(_: RouteError) -> GenerationError {
    GenerationError::Unavailable
}

async fn admitted_generate(
    facade: std::sync::Arc<dyn foretoken_llm_facade::LlmFacade>,
    mut request: vllm_llm::GenerateRequest,
    data_parallel_rank: u32,
) -> Result<TokenStream, GenerationError> {
    request.data_parallel_rank = Some(data_parallel_rank);
    facade
        .generate(request)
        .await
        .map_err(GenerationError::from)
}

// Keeps the frontend-local reservation until the selected model server has accepted or rejected
// the dispatch. Multi-stage calls register cleanup ownership before awaiting generation so an
// admission error can still abort work that the facade may already have started. The model
// server's active-request telemetry owns load after a successful return.
async fn dispatch_generate(
    resolver: &dyn LlmFacadeResolver,
    session: &mut dyn foretoken_router::RouteSession,
    decision: &RouteDecision,
    stage: RouteStage,
    request: vllm_llm::GenerateRequest,
    cleanup: Option<&mut MultiStageCleanup>,
) -> Result<
    (
        std::sync::Arc<dyn foretoken_llm_facade::LlmFacade>,
        TokenStream,
    ),
    GenerationError,
> {
    let result = async {
        let facade = resolver
            .resolve_stage(decision, stage)
            .ok_or(GenerationError::Internal)?;
        if let Some(cleanup) = cleanup {
            cleanup.register(facade.clone(), request.request_id.clone());
        }
        let stream =
            admitted_generate(facade.clone(), request, decision.data_parallel_rank).await?;
        Ok((facade, stream))
    }
    .await;
    session.dispatch_complete(decision);
    result
}

async fn execute_aggregate(
    resolver: &dyn LlmFacadeResolver,
    session: &mut dyn foretoken_router::RouteSession,
    decision: RouteDecision,
    request: vllm_llm::GenerateRequest,
) -> Result<(RouteDecision, TokenStream), GenerationError> {
    let request_id = request.request_id.clone();
    let (facade, stream) = dispatch_generate(
        resolver,
        session,
        &decision,
        RouteStage::Aggregate,
        request,
        None,
    )
    .await?;
    Ok((decision, abort_on_drop(facade, request_id, stream)))
}

// Encoder is a completion barrier rather than a client-visible stream. Keep its cleanup guard
// alive after extracting the descriptor so a failure in later P/D stages can cancel it.
async fn execute_encoder(
    resolver: &dyn LlmFacadeResolver,
    session: &mut dyn foretoken_router::RouteSession,
    decision: RouteDecision,
    request: vllm_llm::GenerateRequest,
) -> Result<(serde_json::Value, MultiStageCleanup), GenerationError> {
    let request = encoder_stage_request(request).map_err(GenerationError::from)?;
    let mut cleanup = MultiStageCleanup::new();
    let (_, stream) = dispatch_generate(
        resolver,
        session,
        &decision,
        RouteStage::Encoder,
        request,
        Some(&mut cleanup),
    )
    .await?;
    let descriptor = consume_encoder(stream)
        .await
        .map_err(GenerationError::from)?;
    Ok((descriptor, cleanup))
}

// Prefill must complete before the same session selects Decode. The cleanup guard bridges that
// handoff and becomes stream-owned only after Decode has been admitted.
async fn execute_pd(
    resolver: &dyn LlmFacadeResolver,
    session: &mut dyn foretoken_router::RouteSession,
    prefill_decision: RouteDecision,
    request: vllm_llm::GenerateRequest,
    descriptor: Option<serde_json::Value>,
    mut cleanup: MultiStageCleanup,
) -> Result<(RouteDecision, TokenStream), GenerationError> {
    let bootstrap = resolver
        .bootstrap_endpoint(&prefill_decision)
        .ok_or(GenerationError::Internal)?;
    let (mut prefill_request, decode_request) = pd_stage_requests(request, &bootstrap)
        .await
        .map_err(GenerationError::from)?;
    if let Some(descriptor) = descriptor {
        inject_ec_transfer_params(&mut prefill_request, descriptor);
    }
    let (_, stream) = dispatch_generate(
        resolver,
        session,
        &prefill_decision,
        RouteStage::Prefill,
        prefill_request,
        Some(&mut cleanup),
    )
    .await?;
    consume_prefill(stream)
        .await
        .map_err(GenerationError::from)?;

    // Started Encoder/Prefill stages remain owned until Decode terminates. The guard covers fresh
    // Decode routing, resolution, admission, cancellation, and abnormal stream termination.
    let decode = session.select_decode().map_err(unavailable)?;
    let decode_decision = decode;
    let (_, stream) = dispatch_generate(
        resolver,
        session,
        &decode_decision,
        RouteStage::Decode,
        decode_request,
        Some(&mut cleanup),
    )
    .await?;
    Ok((decode_decision, cleanup.with_stream(stream)))
}
