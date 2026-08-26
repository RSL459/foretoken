// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! The minimal request data used for route target selection.

use std::sync::Arc;

use foretoken_kv_indexer::{KvPrefixLookup, KvPrefixUnavailableReason};

use crate::RouteTargetId;

/// Request information available to every routing algorithm stage.
#[derive(Clone)]
pub struct RouterRequest {
    /// Requested logical model name.
    pub model: String,
    /// Requested model revision, or `None` when any ready revision may serve it.
    pub revision: Option<String>,
    /// Tokenized vLLM request, including prompt tokens, sampling, multimodal, LoRA, and priority.
    pub generate_request: Arc<vllm_llm::GenerateRequest>,
    /// Route target previously selected for this conversation session, resolved by the caller from
    /// `generate_request.session_id`. `None` when the session has no affinity or is session-less.
    pub session_target_id: Option<RouteTargetId>,
}

impl RouterRequest {
    /// Creates a routing request from the selected model and tokenized generation request.
    pub fn new(
        model: impl Into<String>,
        revision: Option<String>,
        generate_request: Arc<vllm_llm::GenerateRequest>,
    ) -> Self {
        Self {
            model: model.into(),
            revision,
            generate_request,
            session_target_id: None,
        }
    }

    /// Sets the route target previously selected for this conversation session, enabling
    /// session-sticky scorers.
    pub fn with_session_target_id(mut self, session_target_id: Option<RouteTargetId>) -> Self {
        self.session_target_id = session_target_id;
        self
    }

    /// Returns the prompt tokens used by KV-prefix algorithms.
    pub fn prompt_token_ids(&self) -> &[u32] {
        &self.generate_request.prompt_token_ids
    }

    /// Returns the conversation session identity carried by the tokenized request, if any.
    pub fn session_id(&self) -> Option<&str> {
        self.generate_request.session_id.as_deref()
    }

    /// Returns the route target previously selected for this session, when the caller resolved one.
    pub fn session_target_id(&self) -> Option<&str> {
        self.session_target_id.as_ref().map(RouteTargetId::as_str)
    }

    /// Returns the LoRA adapter identity requested by the tokenized request, if any.
    pub fn lora_id(&self) -> Option<&str> {
        self.generate_request
            .lora_request
            .as_ref()
            .map(|lora| lora.lora_name.as_str())
    }

    /// Returns the maximum number of tokens this request may generate.
    pub fn max_new_tokens(&self) -> u32 {
        self.generate_request.sampling_params.max_tokens
    }

    /// Rejects request features whose cache identity is not represented by prompt tokens.
    pub fn kv_prefix_lookup<'a>(
        &'a self,
        route_target_id: &'a str,
        data_parallel_rank: u32,
    ) -> Result<KvPrefixLookup<'a>, KvPrefixUnavailableReason> {
        if self.generate_request.cache_salt.is_some()
            || self.generate_request.lora_request.is_some()
            || self.generate_request.mm_features.is_some()
            || self
                .generate_request
                .sampling_params
                .skip_reading_prefix_cache
                == Some(true)
        {
            return Err(KvPrefixUnavailableReason::UnsupportedRequest);
        }

        Ok(KvPrefixLookup::new(
            route_target_id,
            data_parallel_rank,
            self.prompt_token_ids(),
        ))
    }

    /// Returns the prompt length used for route target input-limit matching.
    pub fn token_count(&self) -> usize {
        self.generate_request.prompt_token_ids.len()
    }
}
