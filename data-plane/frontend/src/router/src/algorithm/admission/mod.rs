// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Request admission before preprocessing and target selection.

mod context;
mod request;

use thiserror::Error;

pub use context::{
    AdmissionContext, AdmissionIdentity, AdmissionModelState, AdmissionModelStatus,
    AdmissionObjectives, AdmissionService, AdmissionStateReader, AdmissionTargetState,
};
pub use request::{
    AdmissionApi, AdmissionInput, AdmissionInputKind, AdmissionMedia, AdmissionOperation,
    AdmissionOutput, AdmissionRequest, AdmissionTokenCount,
};

// Stateful rules receive their parameters before any runtime resources are published.
declare_router_algorithms! {
    descriptor = AdmissionDescriptor;
    factory = from_parameters;
    allow_all => AllowAllAdmission = "allow_all",
    concurrency => ConcurrencyAdmission = "concurrency",
}

/// Accepts complete requests and owns any admission waiting and capacity reservations.
/// A successful result already holds its resources; dropping the future cancels its waiter.
#[async_trait::async_trait]
pub trait RouteAdmission: Send + Sync {
    /// Requires the runtime to check model preparation before admission, without waiting for it.
    fn requires_ready_runtime(&self) -> bool {
        false
    }

    /// Reserves one resident HTTP request before body extraction, without waiting.
    /// A resource-free permit leaves HTTP intake behavior unchanged.
    fn try_reserve_request(&self) -> Result<AdmissionPermit, AdmissionError> {
        Ok(AdmissionPermit::default())
    }

    /// Reserves the entire request weight atomically, waiting only within its original budget.
    async fn admit(
        &self,
        request: &AdmissionRequest,
        context: &AdmissionContext<'_>,
    ) -> Result<AdmissionPermit, AdmissionError>;

    /// Wakes admission waiters on shutdown without revoking permits held by running work.
    fn close(&self) {}
}

/// Algorithm-owned resources backing an admission permit. Drop releases the remaining units.
/// Implementations transfer ownership when splitting; they must not acquire capacity again.
pub trait AdmissionReservation: Send {
    /// Transfers one already-reserved batch unit to a generation child.
    fn split_one(&mut self) -> Box<dyn AdmissionReservation>;
}

/// Ownership transferred from an admission rule through preprocessing and execution.
/// Default permits represent accepted work with no resources to release.
#[derive(Default)]
pub struct AdmissionPermit {
    reservation: Option<Box<dyn AdmissionReservation>>,
}

impl AdmissionPermit {
    /// Takes ownership of a rule's complete reservation, releasing it when the permit is dropped.
    pub fn new(reservation: impl AdmissionReservation + 'static) -> Self {
        Self {
            reservation: Some(Box::new(reservation)),
        }
    }

    /// Reports whether work must retain this permit until its reserved resources can be released.
    pub fn is_reserved(&self) -> bool {
        self.reservation.is_some()
    }

    /// Transfers one reserved unit to a child; unrestricted permits remain resource-free.
    pub fn split_one(&mut self) -> Self {
        Self {
            reservation: self
                .reservation
                .as_mut()
                .map(|reservation| reservation.split_one()),
        }
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
