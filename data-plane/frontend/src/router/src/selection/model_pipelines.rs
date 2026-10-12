// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Resolves model and execution-role overrides and retains their independently owned algorithms.

use std::collections::BTreeMap;
use std::sync::Arc;

use foretoken_model_protocol::ModelServerRole;
use serde::{Deserialize, Serialize};

use super::{
    FilterStage, PickerStage, RouterPipeline, RouterPipelineConfig, RouterPipelineConfigError,
    ScorerStage,
};

/// Optional algorithm selections; each present algorithm and its parameters replace the inherited slot.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RouterPipelineOverride {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub filter: Option<FilterStage>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub scorer: Option<ScorerStage>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub picker: Option<PickerStage>,
}

impl RouterPipelineOverride {
    /// Resolves complete algorithm slots without merging parameters across algorithms.
    fn resolve(&self, inherited: &RouterPipelineConfig) -> RouterPipelineConfig {
        RouterPipelineConfig {
            filter: self
                .filter
                .clone()
                .unwrap_or_else(|| inherited.filter.clone()),
            scorer: self
                .scorer
                .clone()
                .unwrap_or_else(|| inherited.scorer.clone()),
            picker: self
                .picker
                .clone()
                .unwrap_or_else(|| inherited.picker.clone()),
        }
    }
}

/// ModelService routing choices, inherited from the frontend and specialized by execution role.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ModelRouterPipeline {
    #[serde(flatten)]
    pub pipeline: RouterPipelineOverride,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub encoder: Option<RouterPipelineOverride>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub prefill: Option<RouterPipelineOverride>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub decode: Option<RouterPipelineOverride>,
}

impl ModelRouterPipeline {
    /// Resolves this model's aggregate and E/P/D choices against the frontend defaults.
    pub fn resolve(&self, inherited: &RouterPipelineConfig) -> [RouterPipelineConfig; 4] {
        let model = self.pipeline.resolve(inherited);
        [
            model.clone(),
            self.encoder
                .as_ref()
                .map_or_else(|| model.clone(), |stage| stage.resolve(&model)),
            self.prefill
                .as_ref()
                .map_or_else(|| model.clone(), |stage| stage.resolve(&model)),
            self.decode
                .as_ref()
                .map_or_else(|| model.clone(), |stage| stage.resolve(&model)),
        ]
    }
}

/// Immutable algorithms for one runtime generation, isolated by model and execution role.
/// The runtime publisher activates shared state only after accepting the complete generation.
pub struct RouterPipelines<C: Send + 'static = ()> {
    default: Arc<RouterPipeline<C>>,
    models: BTreeMap<String, [Arc<RouterPipeline<C>>; 4]>,
}

impl<C: Send + 'static> RouterPipelines<C> {
    /// Wraps a caller-provided pipeline for all models and roles without changing its custom context.
    pub fn new(pipeline: impl Into<Arc<RouterPipeline<C>>>) -> Self {
        Self {
            default: pipeline.into(),
            models: BTreeMap::new(),
        }
    }

    /// Returns the resolved algorithms for one model's execution role.
    pub(crate) fn get(&self, model: &str, role: ModelServerRole) -> &Arc<RouterPipeline<C>> {
        let index = match role {
            ModelServerRole::Aggregate => 0,
            ModelServerRole::Encoder => 1,
            ModelServerRole::Prefill => 2,
            ModelServerRole::Decode => 3,
        };
        self.models
            .get(model)
            .map_or(&self.default, |stages| &stages[index])
    }

    /// Commits scorer settings at the existing atomic runtime-publication boundary.
    pub fn activate(&self, version: u64) {
        self.default.activate(version);
        for stages in self.models.values() {
            for pipeline in stages {
                pipeline.activate(version);
            }
        }
    }
}

impl RouterPipelines {
    /// Builds a complete model/role generation, reusing history only from the same model and role.
    /// Callers supply resolved configs and retain the previous published set if construction fails.
    pub fn build(
        default: &RouterPipelineConfig,
        models: BTreeMap<String, [RouterPipelineConfig; 4]>,
        previous: Option<&Self>,
    ) -> Result<Self, RouterPipelineConfigError> {
        let fallback = match previous {
            Some(previous) => default.rebuild(&previous.default)?,
            None => default.build()?,
        };
        let mut compiled = BTreeMap::new();
        for (model, configs) in models {
            let old = previous.and_then(|previous| previous.models.get(&model));
            let mut stages = Vec::with_capacity(4);
            for (index, config) in configs.into_iter().enumerate() {
                let pipeline = match old {
                    Some(stages) => config.rebuild(&stages[index]),
                    None => config.build(),
                }
                .map_err(|source| RouterPipelineConfigError::ModelStage {
                    model: model.clone(),
                    stage: ["aggregate", "encoder", "prefill", "decode"][index],
                    source: Box::new(source),
                })?;
                stages.push(Arc::new(pipeline));
            }
            compiled.insert(
                model,
                stages
                    .try_into()
                    .unwrap_or_else(|_| unreachable!("four role configurations")),
            );
        }
        Ok(Self {
            default: Arc::new(fallback),
            models: compiled,
        })
    }
}
