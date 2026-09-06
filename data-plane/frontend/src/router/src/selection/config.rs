// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Configured Filter, Scorer, and Picker selection.

use std::fmt;
use std::str::FromStr;
use std::sync::Arc;

use serde::{Deserialize, Deserializer, Serialize, Serializer};
use thiserror::Error;

use crate::algorithm::scorer::CompositeScorer;
use crate::selection::observer::NoopRoutingObserver;
use crate::{RouteFilter, RoutePicker, RouteScorer, RouterPipeline, RoutingObserver};

/// A Filter implementation compiled into this binary and selectable without control-plane changes.
pub struct FilterDescriptor {
    /// Stable configuration name.
    pub name: &'static str,
    /// Constructs the implementation selected by `name`.
    pub factory: fn() -> Arc<dyn RouteFilter>,
}
inventory::collect!(FilterDescriptor);

/// A Scorer implementation compiled into this binary and selectable without control-plane changes.
pub struct ScorerDescriptor {
    /// Stable configuration name.
    pub name: &'static str,
    /// Raw signal families consumed by the formula, used to reject accidental double counting.
    pub signals: &'static [ScorerSignal],
    /// Whether the formula exposes one normalized signal suitable for weighted composition.
    pub composition: ScorerComposition,
    /// Constructs the implementation selected by `name`.
    pub factory: fn() -> Arc<dyn RouteScorer>,
}
inventory::collect!(ScorerDescriptor);

/// One authoritative raw observation family consumed by a scorer formula.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ScorerSignal {
    Prefix,
    OutstandingRequests,
    RunningRequests,
    QueueDepth,
    TokenLoad,
    Load,
    KvCache,
    LoraAffinity,
    MultimodalAffinity,
    SessionAffinity,
}

impl fmt::Display for ScorerSignal {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        let value = match self {
            Self::Prefix => "prefix",
            Self::OutstandingRequests => "outstanding_requests",
            Self::RunningRequests => "running_requests",
            Self::QueueDepth => "queue_depth",
            Self::TokenLoad => "token_load",
            Self::Load => "load",
            Self::KvCache => "kv_cache",
            Self::LoraAffinity => "lora_affinity",
            Self::MultimodalAffinity => "multimodal_affinity",
            Self::SessionAffinity => "session_affinity",
        };
        formatter.write_str(value)
    }
}

/// Declares whether one scorer's normalized values can be mixed with independent components.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ScorerComposition {
    Composable,
    Exclusive,
}

/// A Picker implementation compiled into this binary and selectable without control-plane changes.
pub struct PickerDescriptor {
    /// Stable configuration name.
    pub name: &'static str,
    /// Constructs the implementation selected by `name`.
    pub factory: fn() -> Arc<dyn RoutePicker>,
}
inventory::collect!(PickerDescriptor);

/// One named algorithm selected in the pipeline configuration.
#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub struct AlgorithmName(String);

impl AlgorithmName {
    fn new(value: String) -> Result<Self, RouterPipelineConfigError> {
        if value.is_empty() {
            return Err(RouterPipelineConfigError::EmptyName);
        }
        Ok(Self(value))
    }

    /// Returns the configured stable algorithm name.
    pub fn as_str(&self) -> &str {
        &self.0
    }
}

impl fmt::Display for AlgorithmName {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.0.fmt(formatter)
    }
}

impl FromStr for AlgorithmName {
    type Err = RouterPipelineConfigError;

    fn from_str(value: &str) -> Result<Self, Self::Err> {
        Self::new(value.to_owned())
    }
}

impl Serialize for AlgorithmName {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        serializer.serialize_str(&self.0)
    }
}

impl<'de> Deserialize<'de> for AlgorithmName {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        String::deserialize(deserializer)?
            .parse()
            .map_err(serde::de::Error::custom)
    }
}

/// Configured Filter selection.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(transparent)]
pub struct FilterAlgorithm(AlgorithmName);

/// Configured Scorer selection.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(transparent)]
pub struct ScorerAlgorithm(AlgorithmName);

/// Configured Picker selection.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(transparent)]
pub struct PickerAlgorithm(AlgorithmName);

macro_rules! algorithm_name_wrapper {
    ($type:ident, $default:literal) => {
        impl $type {
            /// Returns this configuration's algorithm name.
            pub fn as_str(&self) -> &str {
                self.0.as_str()
            }
        }

        impl Default for $type {
            fn default() -> Self {
                $default.parse().expect("built-in algorithm name is valid")
            }
        }

        impl FromStr for $type {
            type Err = RouterPipelineConfigError;

            fn from_str(value: &str) -> Result<Self, Self::Err> {
                Ok(Self(value.parse()?))
            }
        }

        impl fmt::Display for $type {
            fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
                self.0.fmt(formatter)
            }
        }
    };
}

algorithm_name_wrapper!(FilterAlgorithm, "allow_all");
algorithm_name_wrapper!(ScorerAlgorithm, "least_loaded");
algorithm_name_wrapper!(PickerAlgorithm, "round_robin");

/// One scorer component and its positive dimensionless influence in the configured composite.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct ScorerConfig {
    /// Compiled scorer selected by stable name.
    pub name: ScorerAlgorithm,
    /// Relative component influence. Weights are renormalized when a signal is unavailable.
    #[serde(default = "default_scorer_weight")]
    pub weight: f64,
}

impl Default for ScorerConfig {
    fn default() -> Self {
        Self {
            name: ScorerAlgorithm::default(),
            weight: default_scorer_weight(),
        }
    }
}

fn default_scorer_weight() -> f64 {
    1.0
}

fn default_scorers() -> Vec<ScorerConfig> {
    vec![ScorerConfig::default()]
}

/// Configured algorithms selected for each Router pipeline stage.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct RouterPipelineConfig {
    /// Filter used before scoring.
    #[serde(default)]
    pub filter: FilterAlgorithm,
    /// Independent scorers combined to rank filtered candidates.
    #[serde(default = "default_scorers")]
    pub scorers: Vec<ScorerConfig>,
    /// Picker used to select one scored candidate.
    #[serde(default)]
    pub picker: PickerAlgorithm,
}

impl Default for RouterPipelineConfig {
    fn default() -> Self {
        Self {
            filter: FilterAlgorithm::default(),
            scorers: default_scorers(),
            picker: PickerAlgorithm::default(),
        }
    }
}

impl RouterPipelineConfig {
    /// Builds the selected Filter, Scorer, and Picker implementations compiled into this binary.
    pub fn build(&self) -> Result<RouterPipeline, RouterPipelineConfigError> {
        self.build_with_observer(Arc::new(NoopRoutingObserver))
    }

    /// Builds the configured pipeline and publishes bounded scorer diagnostics to `observer`.
    pub fn build_with_observer(
        &self,
        observer: Arc<dyn RoutingObserver>,
    ) -> Result<RouterPipeline, RouterPipelineConfigError> {
        validate_descriptors()?;
        let scorer = configured_scorer(&self.scorers, observer.clone())?;
        Ok(RouterPipeline::new(
            filter_factory(self.filter.as_str())?(),
            scorer,
            picker_factory(self.picker.as_str())?(),
        )
        .with_observer(observer))
    }

    /// Validates all compiled descriptors and configured names before serving begins.
    pub fn validate(&self) -> Result<(), RouterPipelineConfigError> {
        self.build().map(|_| ())
    }
}

fn filter_factory(name: &str) -> Result<fn() -> Arc<dyn RouteFilter>, RouterPipelineConfigError> {
    inventory::iter::<FilterDescriptor>
        .into_iter()
        .find(|descriptor| descriptor.name == name)
        .map(|descriptor| descriptor.factory)
        .ok_or_else(|| RouterPipelineConfigError::UnknownAlgorithm {
            category: "filter",
            name: name.to_owned(),
        })
}

fn scorer_descriptor(name: &str) -> Result<&'static ScorerDescriptor, RouterPipelineConfigError> {
    inventory::iter::<ScorerDescriptor>
        .into_iter()
        .find(|descriptor| descriptor.name == name)
        .ok_or_else(|| RouterPipelineConfigError::UnknownAlgorithm {
            category: "scorer",
            name: name.to_owned(),
        })
}

fn configured_scorer(
    configured: &[ScorerConfig],
    observer: Arc<dyn RoutingObserver>,
) -> Result<Arc<dyn RouteScorer>, RouterPipelineConfigError> {
    if configured.is_empty() {
        return Err(RouterPipelineConfigError::EmptyScorers);
    }
    let mut names = std::collections::BTreeSet::new();
    let mut signals = std::collections::BTreeMap::new();
    let mut components = Vec::with_capacity(configured.len());
    for component in configured {
        let name = component.name.as_str();
        if !component.weight.is_finite() || component.weight <= 0.0 {
            return Err(RouterPipelineConfigError::InvalidScorerWeight {
                name: name.to_owned(),
            });
        }
        if !names.insert(name) {
            return Err(RouterPipelineConfigError::DuplicateConfiguredScorer {
                name: name.to_owned(),
            });
        }
        let descriptor = scorer_descriptor(name)?;
        if configured.len() > 1 && descriptor.composition == ScorerComposition::Exclusive {
            return Err(RouterPipelineConfigError::ExclusiveScorer {
                name: name.to_owned(),
            });
        }
        for signal in descriptor.signals {
            if let Some(previous) = signals.insert(*signal, name) {
                return Err(RouterPipelineConfigError::OverlappingScorerSignal {
                    signal: *signal,
                    first: previous.to_owned(),
                    second: name.to_owned(),
                });
            }
        }
        components.push((name.to_owned(), (descriptor.factory)(), component.weight));
    }
    Ok(Arc::new(CompositeScorer::configured(components, observer)) as Arc<dyn RouteScorer>)
}

fn picker_factory(name: &str) -> Result<fn() -> Arc<dyn RoutePicker>, RouterPipelineConfigError> {
    inventory::iter::<PickerDescriptor>
        .into_iter()
        .find(|descriptor| descriptor.name == name)
        .map(|descriptor| descriptor.factory)
        .ok_or_else(|| RouterPipelineConfigError::UnknownAlgorithm {
            category: "picker",
            name: name.to_owned(),
        })
}

fn validate_descriptors() -> Result<(), RouterPipelineConfigError> {
    validate_descriptor_names(
        "filter",
        inventory::iter::<FilterDescriptor>
            .into_iter()
            .map(|descriptor| descriptor.name),
    )?;
    for descriptor in inventory::iter::<ScorerDescriptor> {
        let mut signals = std::collections::BTreeSet::new();
        if let Some(signal) = descriptor
            .signals
            .iter()
            .find(|signal| !signals.insert(**signal))
        {
            return Err(RouterPipelineConfigError::DuplicateDescriptorSignal {
                name: descriptor.name.to_owned(),
                signal: *signal,
            });
        }
    }
    validate_descriptor_names(
        "scorer",
        inventory::iter::<ScorerDescriptor>
            .into_iter()
            .map(|descriptor| descriptor.name),
    )?;
    validate_descriptor_names(
        "picker",
        inventory::iter::<PickerDescriptor>
            .into_iter()
            .map(|descriptor| descriptor.name),
    )
}

fn validate_descriptor_names<'a>(
    category: &'static str,
    names: impl IntoIterator<Item = &'a str>,
) -> Result<(), RouterPipelineConfigError> {
    let mut names = names.into_iter().collect::<Vec<_>>();
    names.sort_unstable();
    if names.iter().any(|name| name.is_empty()) {
        return Err(RouterPipelineConfigError::EmptyDescriptorName { category });
    }
    if let Some(name) = names
        .windows(2)
        .find_map(|names| (names[0] == names[1]).then_some(names[0]))
    {
        return Err(RouterPipelineConfigError::DuplicateDescriptorName {
            category,
            name: name.to_owned(),
        });
    }
    Ok(())
}

/// A pipeline configuration or compiled registry is invalid.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum RouterPipelineConfigError {
    /// A configured name was empty.
    #[error("router algorithm name must not be empty")]
    EmptyName,
    /// No scorer component was configured.
    #[error("router pipeline requires at least one scorer")]
    EmptyScorers,
    /// A configured component weight was not finite and positive.
    #[error("router scorer {name:?} weight must be finite and positive")]
    InvalidScorerWeight { name: String },
    /// The same scorer was configured twice.
    #[error("router scorer {name:?} is configured more than once")]
    DuplicateConfiguredScorer { name: String },
    /// A relative or internally composite policy was mixed with another scorer.
    #[error("router scorer {name:?} is a complete policy and cannot be composed")]
    ExclusiveScorer { name: String },
    /// Two configured formulas consume the same authoritative signal family.
    #[error("router scorers {first:?} and {second:?} both consume {signal}")]
    OverlappingScorerSignal {
        signal: ScorerSignal,
        first: String,
        second: String,
    },
    /// A compiled implementation omitted its name.
    #[error("compiled {category} descriptor has an empty name")]
    EmptyDescriptorName { category: &'static str },
    /// Two compiled implementations claim the same name.
    #[error("duplicate compiled {category} algorithm name {name:?}")]
    DuplicateDescriptorName {
        category: &'static str,
        name: String,
    },
    /// One compiled descriptor declared the same raw signal more than once.
    #[error("compiled scorer {name:?} declares {signal} more than once")]
    DuplicateDescriptorSignal { name: String, signal: ScorerSignal },
    /// The configuration selected no compiled implementation.
    #[error("unknown compiled {category} algorithm {name:?}")]
    UnknownAlgorithm {
        category: &'static str,
        name: String,
    },
}
