// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Kubernetes-backed asynchronous video task endpoints.

use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::{IntoResponse, Response};
use axum::{Json, Router};
use serde_json::json;

use super::ApiState;
use crate::video_task::VideoTaskSubmit;

pub(super) fn router() -> Router<ApiState> {
    Router::new()
        .route("/v1/videos", axum::routing::post(create))
        .route("/v1/videos/{id}", axum::routing::get(status))
        .route("/v1/videos/{id}/content", axum::routing::get(content))
}

async fn create(State(state): State<ApiState>, Json(request): Json<VideoTaskSubmit>) -> Response {
    let Some(client) = state.video_tasks else {
        return StatusCode::NOT_IMPLEMENTED.into_response();
    };
    match client.create(request).await {
        Ok(accepted) => (StatusCode::ACCEPTED, Json(accepted)).into_response(),
        Err(status) => status.into_response(),
    }
}

async fn status(State(state): State<ApiState>, Path(id): Path<String>) -> Response {
    let Some(client) = state.video_tasks else {
        return StatusCode::NOT_IMPLEMENTED.into_response();
    };
    match client.get(&id).await {
        Ok(task) => Json(json!({
            "id": task.metadata.name,
            "namespace": task.metadata.namespace,
            "phase": task.status.phase,
            "reason": task.status.reason,
            "message": task.status.message,
            "status_url": format!("/v1/videos/{id}"),
            "content_url": format!("/v1/videos/{id}/content"),
            "artifact": task.status.artifact,
        }))
        .into_response(),
        Err(status) => status.into_response(),
    }
}

async fn content(State(state): State<ApiState>, Path(id): Path<String>) -> Response {
    let Some(client) = state.video_tasks else {
        return StatusCode::NOT_IMPLEMENTED.into_response();
    };
    match client.content(&id).await {
        Ok(bytes) => ([(axum::http::header::CONTENT_TYPE, "video/mp4")], bytes).into_response(),
        Err(status) => status.into_response(),
    }
}
