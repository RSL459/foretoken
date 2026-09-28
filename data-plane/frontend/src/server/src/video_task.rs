// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

//! Kubernetes-backed asynchronous video task submission and result access.

use std::path::{Path, PathBuf};
use std::sync::Arc;

use axum::http::StatusCode;
use bytes::Bytes;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Clone)]
pub(crate) struct VideoTaskClient {
    client: Client,
    base_url: String,
    namespace: String,
    output_mount: PathBuf,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub(crate) struct VideoTaskSubmit {
    pub model_service_ref: ServiceReference,
    pub request: VideoTaskRequest,
    pub worker: VideoWorker,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
pub(crate) struct ServiceReference {
    pub name: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub(crate) struct VideoTaskRequest {
    pub task: String,
    pub prompt: String,
    pub width: i32,
    pub height: i32,
    pub num_frames: i32,
    pub fps: i32,
    pub num_inference_steps: i32,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub aspect_ratio: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub flow_shift: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub audio_flow_shift: Option<f64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub seed: Option<i64>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub frame_indices: Vec<i32>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub input_files: Vec<VideoInputFile>,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub(crate) struct VideoInputFile {
    pub field: String,
    pub path: String,
    pub content_type: String,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
pub(crate) struct VideoWorker {
    pub image: String,
    pub endpoint: String,
    pub output_claim_name: String,
    pub output_path: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub service_account_name: Option<String>,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct VideoTaskResource {
    pub metadata: TaskMetadata,
    #[serde(default)]
    pub status: VideoTaskStatus,
}

#[derive(Debug, Deserialize)]
pub(crate) struct TaskMetadata {
    pub name: String,
    pub namespace: String,
}

#[derive(Debug, Default, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct VideoTaskStatus {
    #[serde(default)]
    pub phase: String,
    #[serde(default)]
    pub reason: String,
    #[serde(default)]
    pub message: String,
    #[serde(default)]
    pub artifact: Option<VideoArtifact>,
}

#[derive(Debug, Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
pub(crate) struct VideoArtifact {
    pub claim_name: String,
    pub path: String,
}

#[derive(Debug, Serialize)]
pub(crate) struct VideoTaskAccepted {
    pub id: String,
    pub status_url: String,
    pub content_url: String,
}

impl VideoTaskClient {
    pub(crate) fn from_service_account() -> Option<Arc<Self>> {
        let host = std::env::var("KUBERNETES_SERVICE_HOST").ok()?;
        let port = std::env::var("KUBERNETES_SERVICE_PORT").ok()?;
        let namespace =
            std::fs::read_to_string("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
                .ok()?;
        let token =
            std::fs::read_to_string("/var/run/secrets/kubernetes.io/serviceaccount/token").ok()?;
        let ca = std::fs::read("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt").ok()?;
        let certificate = reqwest::Certificate::from_pem(&ca).ok()?;
        let mut headers = reqwest::header::HeaderMap::new();
        headers.insert(
            reqwest::header::AUTHORIZATION,
            format!("Bearer {}", token.trim()).parse().ok()?,
        );
        let client = Client::builder()
            .add_root_certificate(certificate)
            .default_headers(headers)
            .build()
            .ok()?;
        Some(Arc::new(Self {
            client,
            base_url: format!("https://{host}:{port}"),
            namespace: namespace.trim().to_owned(),
            output_mount: PathBuf::from(std::env::var("FORETOKEN_VIDEO_TASK_OUTPUT_MOUNT").ok()?),
        }))
    }

    pub(crate) async fn create(
        &self,
        submit: VideoTaskSubmit,
    ) -> Result<VideoTaskAccepted, StatusCode> {
        let id = format!("video-{}", Uuid::new_v4());
        let url = self.resource_url(&id);
        let body = serde_json::json!({
            "apiVersion": "inference.foretoken.io/v1alpha1",
            "kind": "VideoTask",
            "metadata": {"name": id},
            "spec": submit,
        });
        self.client
            .post(url)
            .json(&body)
            .send()
            .await
            .map_err(|_| StatusCode::BAD_GATEWAY)?
            .error_for_status()
            .map_err(|_| StatusCode::BAD_REQUEST)?;
        Ok(VideoTaskAccepted {
            id: id.clone(),
            status_url: format!("/v1/videos/{id}"),
            content_url: format!("/v1/videos/{id}/content"),
        })
    }

    pub(crate) async fn get(&self, id: &str) -> Result<VideoTaskResource, StatusCode> {
        self.client
            .get(self.resource_url(id))
            .send()
            .await
            .map_err(|_| StatusCode::BAD_GATEWAY)?
            .json()
            .await
            .map_err(|_| StatusCode::BAD_GATEWAY)
    }

    pub(crate) async fn content(&self, id: &str) -> Result<Bytes, StatusCode> {
        let task = self.get(id).await?;
        if task.status.phase != "Succeeded" {
            return Err(if task.status.phase.is_empty() {
                StatusCode::NOT_FOUND
            } else {
                StatusCode::CONFLICT
            });
        }
        let artifact = task
            .status
            .artifact
            .ok_or(StatusCode::INTERNAL_SERVER_ERROR)?;
        let path = self.output_mount.join(&artifact.path);
        if !path.starts_with(&self.output_mount) || !Path::new(&artifact.path).is_relative() {
            return Err(StatusCode::INTERNAL_SERVER_ERROR);
        }
        tokio::fs::read(path)
            .await
            .map(Bytes::from)
            .map_err(|_| StatusCode::NOT_FOUND)
    }

    fn resource_url(&self, id: &str) -> String {
        format!(
            "{}/apis/inference.foretoken.io/v1alpha1/namespaces/{}/videotasks/{}",
            self.base_url, self.namespace, id
        )
    }
}
