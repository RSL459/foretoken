// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Unrestricted admission without runtime accounting.

use std::sync::Arc;

use super::Admission;

/// Resolves the parameter-free rule without allocating admission state.
pub(super) fn build(parameters: serde_json::Value) -> Result<Option<Arc<Admission>>, String> {
    if parameters
        .as_object()
        .is_some_and(|parameters| parameters.is_empty())
    {
        Ok(None)
    } else {
        Err("allow_all admission accepts no parameters".into())
    }
}
