// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Router pipeline registry and configuration tests.

use foretoken_router::{
    FilterAlgorithm, PickerAlgorithm, RouterPipelineConfig, RouterPipelineConfigError,
    ScorerAlgorithm, ScorerConfig,
};

// Protects the complete descriptor registry and default pipeline from invalid registration.
#[test]
fn compiled_registry_and_default_pipeline_validate() {
    RouterPipelineConfig::default().validate().unwrap();
}

// Protects user configuration from empty or unavailable algorithm names while allowing opaque names.
#[test]
fn empty_and_unknown_names_are_explicit_errors() {
    assert_eq!(
        "".parse::<FilterAlgorithm>(),
        Err(RouterPipelineConfigError::EmptyName)
    );
    assert!("community-scorer".parse::<ScorerAlgorithm>().is_ok());
    let unknown = RouterPipelineConfig {
        filter: "allow_all".parse().unwrap(),
        scorers: vec![ScorerConfig {
            name: "community-scorer".parse().unwrap(),
            weight: 1.0,
        }],
        picker: PickerAlgorithm::default(),
    };
    assert!(matches!(
        unknown.build(),
        Err(RouterPipelineConfigError::UnknownAlgorithm {
            category: "scorer",
            name,
        }) if name == "community-scorer"
    ));

    let configured = |names: &[&str]| RouterPipelineConfig {
        filter: FilterAlgorithm::default(),
        scorers: names
            .iter()
            .map(|name| ScorerConfig {
                name: name.parse().unwrap(),
                weight: 1.0,
            })
            .collect(),
        picker: PickerAlgorithm::default(),
    };
    assert!(matches!(
        configured(&["least_loaded", "least_loaded"]).validate(),
        Err(RouterPipelineConfigError::DuplicateConfiguredScorer { .. })
    ));
    assert!(matches!(
        configured(&["least_loaded", "uniform"]).validate(),
        Err(RouterPipelineConfigError::ExclusiveScorer { .. })
    ));
}
