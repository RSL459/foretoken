# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Own short-lived file publishers and address the platform's persistent origin."""

from __future__ import annotations

import json
import math
import time
import uuid
from importlib.resources import files
from urllib.parse import unquote, urlsplit

from foretoken.cluster_build import ClusterBuilder
from foretoken.kubernetes import Kubectl, timeout_seconds
from foretoken.manifest import DeploymentError, ResourceRef

_BINDING_LABEL = "inference.foretoken.io/application-publisher-binding"


def remove_application_jobs(kubectl: Kubectl, binding: str, timeout: str) -> None:
    """Stop abandoned writers before their workstation reuses its compiler output."""
    kubectl.run(
        [
            "delete",
            "jobs",
            "--all-namespaces",
            "--selector",
            f"foretoken.io/application-files=publisher,{_BINDING_LABEL}={binding}",
            "--ignore-not-found",
            "--cascade=foreground",
            "--wait=true",
            "--timeout=" + timeout,
        ]
    )


class ApplicationFiles:
    """Resolve the installed file origin without taking ownership of model storage."""

    def __init__(self, kubectl: Kubectl, namespace: str) -> None:
        self.kubectl = kubectl
        self.namespace = namespace
        configurations = kubectl.list_resources(
            ("configmaps",),
            namespace,
            label_selector="foretoken.io/application-files=configuration",
        )
        if len(configurations) != 1:
            raise DeploymentError(
                "application file storage is unavailable; update the source installation"
            )
        configuration = configurations[0]
        self.name = configuration["metadata"]["name"]
        data = configuration["data"]
        self.claim = data["claim"]
        self.endpoint = data["endpoint"]
        self.client_image = data["clientImage"]
        self.mount = data["storageMount"]

    def prepare(self, timeout: str) -> None:
        """Wait for the file origin and select its volume's current publisher node."""
        kubectl, namespace = self.kubectl, self.namespace
        kubectl.rollout_status(ResourceRef("Deployment", self.name, namespace), timeout)
        self.claim_uid = kubectl.get("pvc", self.claim, namespace)["metadata"]["uid"]
        deployment = kubectl.get("deployment", self.name, namespace)
        self.pull_secrets = tuple(
            secret["name"]
            for secret in deployment["spec"]["template"]["spec"].get(
                "imagePullSecrets", []
            )
        )
        selector = ",".join(
            f"{key}={value}"
            for key, value in deployment["spec"]["selector"]["matchLabels"].items()
        )
        pods = kubectl.list_resources(("pods",), namespace, label_selector=selector)
        ready = [
            pod
            for pod in pods
            if not pod["metadata"].get("deletionTimestamp")
            and any(
                condition["type"] == "Ready" and condition["status"] == "True"
                for condition in pod.get("status", {}).get("conditions", [])
            )
        ]
        if len(ready) != 1:
            raise DeploymentError(
                "application file server has no single ready publisher node"
            )
        self.node = ready[0]["spec"]["nodeName"]

    def reference(self, component: str, revision: str) -> str:
        """Return the immutable HTTP directory selected by an application consumer."""
        return f"{self.endpoint}/{component}/{revision}"

    def publish(
        self,
        builder: ClusterBuilder | None,
        source: str,
        component: str,
        revision: str,
        previous: str,
        references: set[str] | None,
        *,
        timeout: str,
        credentials_secret: str = "",
    ) -> None:
        """Publish a compiler export or import an HTTP release archive before workload rollout.

        A builder supplies source files; without one, the Job imports all release components.
        Source callers hold their binding lock and stop abandoned writers before reusing output.
        """
        script = files("foretoken").joinpath("application_publish.py").read_text()
        binding = builder.binding if builder is not None else "release-" + uuid.uuid4().hex
        destination = f"{self.mount}/{component}/{revision}"
        if builder is None:
            script = f"namespace = {{'__name__': 'application_publish'}}\nexec({script!r}, namespace)\npublish = namespace['publish']\n" + '''
import os
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen
with tempfile.TemporaryDirectory(dir="/tmp") as temporary:
    archive = Path(temporary) / "applications.tar.gz"
    headers = {}
    if credential := os.environ.get("FORETOKEN_RELEASE_AUTHORIZATION"):
        headers["Authorization"] = credential
    with urlopen(Request(sys.argv[1], headers=headers)) as response, archive.open("wb") as output:
        shutil.copyfileobj(response, output)
    payload = Path(temporary) / "payload"
    with tarfile.open(archive) as package:
        package.extractall(payload, filter="data")
    for component in ("control-plane", "frontend", "model-server"):
        publish(payload / component, Path(sys.argv[2]) / component / sys.argv[3], sys.argv[4], None)
'''
            destination = self.mount
        keep = (
            None
            if references is None
            else sorted(
                {
                    unquote(urlsplit(reference).path).rstrip("/").rsplit("/", 1)[-1]
                    for reference in references
                    if reference
                }
            )
        )
        name = "foretoken-publish-" + uuid.uuid4().hex[:12]
        seconds = math.ceil(timeout_seconds(timeout))
        labels = {
            "foretoken.io/application-files": "publisher",
            _BINDING_LABEL: binding,
        }
        mounts = [{"name": "applications", "mountPath": self.mount}]
        volumes = [{"name": "applications", "persistentVolumeClaim": {"claimName": self.claim}}]
        command = ["python", "-c", script, source, destination]
        if builder is not None:
            mounts.insert(0, {"name": "compiler", "mountPath": builder.mount, "readOnly": True})
            volumes.insert(0, {"name": "compiler", "persistentVolumeClaim": {"claimName": builder.claim, "readOnly": True}})
            command.extend([binding, f"{self.mount}/{component}/{previous}" if previous else "", json.dumps(keep)])
        else:
            mounts.append({"name": "temporary", "mountPath": "/tmp"})
            volumes.append({"name": "temporary", "emptyDir": {}})
            command.extend([revision, binding])
        job = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": name,
                "namespace": self.namespace,
                "labels": labels,
                "ownerReferences": [
                    {
                        "apiVersion": "v1",
                        "kind": "PersistentVolumeClaim",
                        "name": self.claim,
                        "uid": self.claim_uid,
                    }
                ],
            },
            "spec": {
                "backoffLimit": 0,
                "activeDeadlineSeconds": seconds,
                "ttlSecondsAfterFinished": seconds,
                "template": {
                    "metadata": {"labels": labels},
                    "spec": {
                        "restartPolicy": "Never",
                        "automountServiceAccountToken": False,
                        "imagePullSecrets": [
                            {"name": secret} for secret in self.pull_secrets
                        ],
                        "affinity": {
                            "nodeAffinity": {
                                "requiredDuringSchedulingIgnoredDuringExecution": {
                                    "nodeSelectorTerms": [
                                        {
                                            "matchFields": [
                                                {
                                                    "key": "metadata.name",
                                                    "operator": "In",
                                                    "values": [self.node],
                                                }
                                            ]
                                        }
                                    ],
                                }
                            }
                        },
                        "securityContext": {
                            "runAsNonRoot": True,
                            "runAsUser": 1000,
                            "runAsGroup": 1000,
                            "fsGroup": 1000,
                            "fsGroupChangePolicy": "OnRootMismatch",
                            "seccompProfile": {"type": "RuntimeDefault"},
                        },
                        "containers": [
                            {
                                "name": "publish",
                                "image": self.client_image,
                                "command": command,
                                "terminationMessagePolicy": "FallbackToLogsOnError",
                                "securityContext": {
                                    "allowPrivilegeEscalation": False,
                                    "readOnlyRootFilesystem": True,
                                    "capabilities": {"drop": ["ALL"]},
                                },
                                "volumeMounts": mounts,
                            }
                        ],
                        "volumes": volumes,
                    },
                },
            },
        }
        if credentials_secret:
            job["spec"]["template"]["spec"]["containers"][0]["env"] = [{
                "name": "FORETOKEN_RELEASE_AUTHORIZATION",
                "valueFrom": {"secretKeyRef": {"name": credentials_secret, "key": "authorization"}},
            }]
        self.kubectl.run(["create", "-f", "-"], input_text=json.dumps(job))
        deadline = time.monotonic() + seconds
        while True:
            current = self.kubectl.get("job", name, self.namespace)
            conditions = current.get("status", {}).get("conditions", [])
            if any(
                c["type"] == "Complete" and c["status"] == "True" for c in conditions
            ):
                self.kubectl.run(
                    [
                        "delete",
                        "job",
                        name,
                        "-n",
                        self.namespace,
                        "--cascade=foreground",
                        "--wait=true",
                        "--timeout=" + timeout,
                    ]
                )
                return
            failed = next(
                (
                    c
                    for c in conditions
                    if c["type"] == "Failed" and c["status"] == "True"
                ),
                None,
            )
            if failed is not None:
                messages = [failed.get("message", failed.get("reason", "Job failed"))]
                for pod in self.kubectl.list_resources(
                    ("pods",),
                    self.namespace,
                    label_selector="batch.kubernetes.io/job-name=" + name,
                ):
                    for container in pod.get("status", {}).get("containerStatuses", []):
                        if (
                            message := container.get("state", {})
                            .get("terminated", {})
                            .get("message")
                        ):
                            messages.append(message)
                raise DeploymentError(
                    f"application publication {self.namespace}/{name} failed: "
                    + "\n".join(messages)
                )
            if time.monotonic() >= deadline:
                raise DeploymentError(
                    f"application publication {self.namespace}/{name} did not finish within {timeout}"
                )
            time.sleep(1)
