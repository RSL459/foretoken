// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Process-local admission shared by successive routing generations.

use std::sync::Arc;
use std::time::{Duration, Instant};

use serde::Deserialize;
use thiserror::Error;
use tokio::sync::{OwnedSemaphorePermit, Semaphore, TryAcquireError};

use crate::metrics::{AdmissionRejectionLabels, METRICS};

#[derive(Deserialize)]
#[serde(rename_all = "camelCase", deny_unknown_fields)]
struct Parameters {
    max_concurrent_requests: u32,
    #[serde(default)]
    max_queued_requests: u32,
    queue_timeout: Option<String>,
}

/// One frontend's execution, waiting, and resident-request budgets.
/// The pipeline retains this owner across serving-snapshot replacements.
pub struct Admission {
    capacity: u32,
    active: Arc<Semaphore>,
    queued: Arc<Semaphore>,
    resident: Arc<Semaphore>,
    queue_timeout: Option<Duration>,
}

impl Admission {
    /// Resolves the concurrency stage once at process startup, without guessing capacity.
    pub fn from_parameters(parameters: serde_json::Value) -> Result<Arc<Self>, String> {
        let parameters: Parameters = serde_json::from_value(parameters)
            .map_err(|error| format!("routerPipeline.admission.parameters: {error}"))?;
        let capacity = parameters.max_concurrent_requests;
        if capacity == 0 {
            return Err(
                "routerPipeline.admission.parameters.maxConcurrentRequests must be positive".into(),
            );
        }
        let resident = (capacity as usize)
            .checked_add(parameters.max_queued_requests as usize)
            .filter(|total| *total <= Semaphore::MAX_PERMITS)
            .ok_or("routerPipeline.admission request limits exceed supported capacity")?;
        let queue_timeout = parameters
            .queue_timeout
            .map(|value| {
                humantime::parse_duration(&value)
                    .map_err(|error| {
                        format!("routerPipeline.admission.parameters.queueTimeout: {error}")
                    })
                    .and_then(|duration| {
                        if duration.is_zero() {
                            Err(
                                "routerPipeline.admission.parameters.queueTimeout must be positive"
                                    .into(),
                            )
                        } else {
                            Ok(duration)
                        }
                    })
            })
            .transpose()?;
        Ok(Arc::new(Self {
            capacity,
            active: Arc::new(Semaphore::new(capacity as usize)),
            queued: Arc::new(Semaphore::new(parameters.max_queued_requests as usize)),
            resident: Arc::new(Semaphore::new(resident)),
            queue_timeout,
        }))
    }

    /// Reserves an HTTP request before body extraction; the response retains the permit.
    pub fn try_reserve_request(&self) -> Result<AdmissionPermit, AdmissionError> {
        self.resident
            .clone()
            .try_acquire_owned()
            .map(|permit| AdmissionPermit::counted(permit, PermitKind::Resident))
            .map_err(|error| match error {
                TryAcquireError::Closed => AdmissionError::Closed,
                TryAcquireError::NoPermits => rejected("resident_full", AdmissionError::Overloaded),
            })
    }

    /// Admits a complete generation batch or waits within both queue and request budgets.
    /// Canceling this future drops its semaphore waiter and queue observation.
    pub async fn acquire(
        &self,
        units: u32,
        deadline: tokio::time::Instant,
    ) -> Result<AdmissionPermit, AdmissionError> {
        if units == 0 || units > self.capacity {
            return Err(rejected("batch_too_large", AdmissionError::BatchTooLarge));
        }
        if tokio::time::Instant::now() >= deadline {
            return Err(AdmissionError::DeadlineExceeded);
        }
        match self.active.clone().try_acquire_many_owned(units) {
            Ok(permit) => return Ok(AdmissionPermit::counted(permit, PermitKind::Active)),
            Err(TryAcquireError::Closed) => return Err(AdmissionError::Closed),
            Err(TryAcquireError::NoPermits) => {}
        }
        let queued =
            self.queued
                .clone()
                .try_acquire_many_owned(units)
                .map_err(|error| match error {
                    TryAcquireError::Closed => AdmissionError::Closed,
                    TryAcquireError::NoPermits => {
                        rejected("queue_full", AdmissionError::Overloaded)
                    }
                })?;
        let started = tokio::time::Instant::now();
        let _waiting = QueueWait {
            _permit: AdmissionPermit::counted(queued, PermitKind::Queued),
            started: started.into_std(),
        };
        let expires = self
            .queue_timeout
            .and_then(|duration| started.checked_add(duration))
            .map_or(deadline, |queue_deadline| queue_deadline.min(deadline));
        let permit = tokio::select! {
            biased;
            _ = tokio::time::sleep_until(expires) => None,
            permit = self.active.clone().acquire_many_owned(units) => {
                Some(permit.map_err(|_| AdmissionError::Closed)?)
            }
        };
        // A ready semaphore can win before the timer driver observes an elapsed deadline.
        match permit {
            Some(permit) if tokio::time::Instant::now() < expires => {
                Ok(AdmissionPermit::counted(permit, PermitKind::Active))
            }
            _ if expires == deadline => Err(AdmissionError::DeadlineExceeded),
            _ => Err(rejected("queue_timeout", AdmissionError::QueueTimeout)),
        }
    }

    /// Wakes pending requests on process shutdown while accepted work keeps its permits.
    pub fn close(&self) {
        self.resident.close();
        self.queued.close();
        self.active.close();
    }
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
/// Default permits preserve the disabled stage's existing behavior.
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

struct QueueWait {
    _permit: AdmissionPermit,
    started: Instant,
}

impl Drop for QueueWait {
    fn drop(&mut self) {
        METRICS
            .admission_wait
            .observe(self.started.elapsed().as_secs_f64());
    }
}

fn rejected(reason: &'static str, error: AdmissionError) -> AdmissionError {
    METRICS
        .admission_rejected
        .get_or_create(&AdmissionRejectionLabels { reason })
        .inc();
    error
}
