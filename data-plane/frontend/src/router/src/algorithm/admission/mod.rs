// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Admission rules applied before preprocessing and target selection.

mod allow_all;
mod concurrency;

use std::sync::Arc;

use thiserror::Error;
use tokio::sync::OwnedSemaphorePermit;

use crate::metrics::METRICS;
use crate::{AdmissionStage, RouterPipelineConfigError};

pub use concurrency::Admission;

/// Builds the selected admission rule once; unrestricted admission needs no runtime state.
pub(crate) fn build(
    stage: &AdmissionStage,
) -> Result<Option<Arc<Admission>>, RouterPipelineConfigError> {
    let parameters = serde_json::Value::Object(stage.parameters.clone());
    match stage.algorithm.as_str() {
        "allow_all" => allow_all::build(parameters),
        "concurrency" => Admission::from_parameters(parameters).map(Some),
        _ => {
            return Err(RouterPipelineConfigError::UnknownAlgorithm {
                category: "admission",
                name: stage.algorithm.to_string(),
            });
        }
    }
    .map_err(|message| RouterPipelineConfigError::InvalidParameters {
        name: format!("admission.{}", stage.algorithm),
        message,
    })
}

/// Admission outcomes translated by protocol adapters before response headers.
#[derive(Clone, Copy, Debug, Error, PartialEq, Eq)]
pub enum AdmissionError {
    #[error("generation service is overloaded")]
    Overloaded,
    #[error("admission queue timeout exceeded")]
    QueueTimeout,
    #[error("request deadline exceeded")]
    DeadlineExceeded,
    #[error("request fan-out exceeds configured admission concurrency")]
    BatchTooLarge,
    #[error("generation admission is closed")]
    Closed,
}

#[derive(Default)]
enum PermitKind {
    #[default]
    Active,
    Queued,
    Resident,
}

/// Ownership of admitted work, queued units, or a resident HTTP request.
/// Default permits represent unrestricted admission.
#[derive(Default)]
pub struct AdmissionPermit {
    permit: Option<OwnedSemaphorePermit>,
    kind: PermitKind,
}

impl AdmissionPermit {
    fn counted(permit: OwnedSemaphorePermit, kind: PermitKind) -> Self {
        let value = Self {
            permit: Some(permit),
            kind,
        };
        value.gauge().inc_by(value.units());
        value
    }

    /// Transfers one already-reserved batch unit to its generation child without reacquiring.
    pub fn split_one(&mut self) -> Self {
        Self {
            permit: self.permit.as_mut().map(|permit| {
                permit
                    .split(1)
                    .expect("generation batch has a reserved unit for each child")
            }),
            kind: PermitKind::Active,
        }
    }

    fn units(&self) -> i64 {
        self.permit
            .as_ref()
            .map_or(0, |permit| permit.num_permits() as i64)
    }

    fn gauge(&self) -> &prometheus_client::metrics::gauge::Gauge {
        match self.kind {
            PermitKind::Active => &METRICS.admission_active,
            PermitKind::Queued => &METRICS.admission_queued,
            PermitKind::Resident => &METRICS.admission_resident,
        }
    }
}

impl Drop for AdmissionPermit {
    fn drop(&mut self) {
        if self.permit.is_some() {
            self.gauge().dec_by(self.units());
        }
    }
}
