# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Own node-local compiler volumes and their dedicated upstream provisioner."""

from __future__ import annotations

import json
import time
from typing import Any

import yaml

from foretoken.kubernetes import Kubectl, resource_ref, timeout_seconds
from foretoken.manifest import DeploymentError

SOURCE_BUILD_UID = 65531
SOURCE_BUILD_STORAGE_CLASS = "foretoken-source-build"
SOURCE_BUILD_PROVISIONER = "inference.foretoken.io/source-build"
SOURCE_BUILD_PROVISIONER_IMAGE = "docker.io/rancher/local-path-provisioner:v0.0.37"

_OWNER_LABEL = "inference.foretoken.io/source-build-storage"
_NODE_DIRECTORY = "/var/lib/foretoken/source-build"
_NAMESPACED_KINDS = (
    "deployments",
    "configmaps",
    "serviceaccounts",
    "roles",
    "rolebindings",
)
_CLUSTER_KINDS = ("storageclasses", "clusterroles", "clusterrolebindings")


def _resources(
    namespace: str,
    tools_image: str,
    provisioner_image: str,
    pull_secrets: tuple[str, ...],
) -> list[dict[str, Any]]:
    """Render the dedicated local-path-provisioner v0.0.37 resources and helper configuration."""
    name = SOURCE_BUILD_STORAGE_CLASS
    labels = {
        _OWNER_LABEL: namespace,
        "app.kubernetes.io/name": name,
        "app.kubernetes.io/managed-by": "foretoken",
    }
    helper = {
        "apiVersion": "v1",
        "kind": "Pod",
        "metadata": {"name": "helper-pod"},
        "spec": {
            "priorityClassName": "system-node-critical",
            "imagePullSecrets": [{"name": secret} for secret in pull_secrets],
            "tolerations": [
                {
                    "key": "node.kubernetes.io/disk-pressure",
                    "operator": "Exists",
                    "effect": "NoSchedule",
                }
            ],
            "containers": [
                {
                    "name": "helper-pod",
                    "image": tools_image,
                    "imagePullPolicy": "IfNotPresent",
                    "env": [{"name": "NVIDIA_VISIBLE_DEVICES", "value": "void"}],
                }
            ],
        },
    }
    resources: list[dict[str, Any]] = [
        {"apiVersion": "v1", "kind": "ServiceAccount"},
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "Role",
            "rules": [
                {
                    "apiGroups": [""],
                    "resources": ["pods"],
                    "verbs": [
                        "get",
                        "list",
                        "watch",
                        "create",
                        "patch",
                        "update",
                        "delete",
                    ],
                }
            ],
        },
        {
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "ClusterRole",
            "rules": [
                {
                    "apiGroups": [""],
                    "resources": [
                        "nodes",
                        "persistentvolumeclaims",
                        "configmaps",
                        "pods",
                        "pods/log",
                    ],
                    "verbs": ["get", "list", "watch"],
                },
                {
                    "apiGroups": [""],
                    "resources": ["persistentvolumes"],
                    "verbs": [
                        "get",
                        "list",
                        "watch",
                        "create",
                        "patch",
                        "update",
                        "delete",
                    ],
                },
                {
                    "apiGroups": [""],
                    "resources": ["events"],
                    "verbs": ["create", "patch"],
                },
                {
                    "apiGroups": ["storage.k8s.io"],
                    "resources": ["storageclasses"],
                    "verbs": ["get", "list", "watch"],
                },
            ],
        },
        *[
            {
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": kind + "Binding",
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": kind,
                    "name": name,
                },
                "subjects": [
                    {"kind": "ServiceAccount", "name": name, "namespace": namespace}
                ],
            }
            for kind in ("Role", "ClusterRole")
        ],
        {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "data": {
                "config.json": json.dumps(
                    {
                        "nodePathMap": [
                            {
                                "node": "DEFAULT_PATH_FOR_NON_LISTED_NODES",
                                "paths": [_NODE_DIRECTORY],
                            }
                        ]
                    }
                ),
                # A local PV still uses the filesystem beneath its configured node path.
                # Reject NFS before creating a compiler directory or changing its ownership.
                "setup": """#!/bin/sh
set -eu
filesystem=$(stat -f -c %t "$(dirname "$VOL_DIR")")
case "$filesystem" in
    6969) printf 'source build storage requires a non-NFS node filesystem: %s\\n' "$VOL_DIR" >&2; exit 1 ;;
esac
mkdir -p "$VOL_DIR"
chown "$VOL_USER:$VOL_GROUP" "$VOL_DIR"
chmod "$VOL_PERM" "$VOL_DIR"
""",
                "teardown": """#!/bin/sh
set -eu
rm -rf "$VOL_DIR"
""",
                "helperPod.yaml": yaml.safe_dump(helper, sort_keys=False),
            },
        },
        {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {_OWNER_LABEL: namespace}},
                "template": {
                    "metadata": {"labels": labels},
                    "spec": {
                        "serviceAccountName": name,
                        "imagePullSecrets": [
                            {"name": secret} for secret in pull_secrets
                        ],
                        "containers": [
                            {
                                "name": "provisioner",
                                "image": provisioner_image,
                                "imagePullPolicy": "IfNotPresent",
                                "command": [
                                    "local-path-provisioner",
                                    "start",
                                    "--config",
                                    "/etc/config/config.json",
                                    "--provisioner-name",
                                    SOURCE_BUILD_PROVISIONER,
                                    "--configmap-name",
                                    name,
                                    "--service-account-name",
                                    name,
                                ],
                                "env": [
                                    {
                                        "name": "POD_NAMESPACE",
                                        "valueFrom": {
                                            "fieldRef": {
                                                "fieldPath": "metadata.namespace"
                                            }
                                        },
                                    },
                                    {
                                        "name": "CONFIG_MOUNT_PATH",
                                        "value": "/etc/config/",
                                    },
                                    {"name": "HEALTH_PORT", "value": "8080"},
                                    {"name": "NVIDIA_VISIBLE_DEVICES", "value": "void"},
                                ],
                                "ports": [{"name": "health", "containerPort": 8080}],
                                "startupProbe": {
                                    "httpGet": {"path": "/health", "port": "health"},
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 5,
                                    "failureThreshold": 12,
                                },
                                "livenessProbe": {
                                    "httpGet": {"path": "/health", "port": "health"},
                                    "initialDelaySeconds": 10,
                                    "periodSeconds": 10,
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": "/ready", "port": "health"},
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 5,
                                },
                                "volumeMounts": [
                                    {
                                        "name": "config",
                                        "mountPath": "/etc/config/",
                                        "readOnly": True,
                                    }
                                ],
                            }
                        ],
                        "volumes": [{"name": "config", "configMap": {"name": name}}],
                    },
                },
            },
        },
        {
            "apiVersion": "storage.k8s.io/v1",
            "kind": "StorageClass",
            "metadata": {
                "annotations": {
                    "defaultVolumeType": "local",
                    "storageclass.kubernetes.io/is-default-class": "false",
                }
            },
            "provisioner": SOURCE_BUILD_PROVISIONER,
            "volumeBindingMode": "WaitForFirstConsumer",
            "reclaimPolicy": "Delete",
            "parameters": {
                "userPattern": str(SOURCE_BUILD_UID),
                "groupPattern": "1000",
                "permPattern": "2775",
            },
        },
    ]
    for document in resources:
        metadata = document.setdefault("metadata", {})
        metadata.update(name=name, labels=labels)
        if document["kind"] not in {
            "ClusterRole",
            "ClusterRoleBinding",
            "StorageClass",
        }:
            metadata["namespace"] = namespace
    return resources


def ensure_build_storage(
    kubectl: Kubectl,
    namespace: str,
    tools_image: str,
    provisioner_image: str,
    pull_secrets: tuple[str, ...],
    timeout: str,
) -> str:
    """Prepare shared source storage before builds and return its non-default StorageClass.

    The source installation owns this dependency across checkout bindings and
    supplies its selected images and namespace-local pull secrets.
    """
    resources = _resources(namespace, tools_image, provisioner_image, pull_secrets)
    for document in resources:
        ref = resource_ref(document)
        existing = kubectl.get_if_exists(ref.kind, ref.name, ref.namespace)
        if (
            existing is not None
            and existing["metadata"].get("labels", {}).get(_OWNER_LABEL) != namespace
        ):
            raise DeploymentError(
                f"cannot prepare source storage: {ref.display_name} already exists outside this installation"
            )
    if not kubectl.exists("namespace", namespace):
        kubectl.apply(
            yaml.safe_dump(
                {
                    "apiVersion": "v1",
                    "kind": "Namespace",
                    "metadata": {"name": namespace},
                }
            )
        )
    kubectl.apply(yaml.safe_dump_all(resources, sort_keys=False))
    deployment = next(
        document for document in resources if document["kind"] == "Deployment"
    )
    kubectl.rollout_status(resource_ref(deployment), timeout)
    return SOURCE_BUILD_STORAGE_CLASS


def managed_build_storage_resources(
    kubectl: Kubectl, namespace: str
) -> tuple[dict[str, Any], ...]:
    """Discover owned storage resources, including a bootstrap without workstation state."""
    selector = f"{_OWNER_LABEL}={namespace}"
    return (
        *kubectl.list_resources(_NAMESPACED_KINDS, namespace, label_selector=selector),
        *kubectl.list_cluster_resources(_CLUSTER_KINDS, label_selector=selector),
    )


def remove_build_storage(
    kubectl: Kubectl, namespace: str, timeout: str
) -> tuple[str, str]:
    """Remove owned provisioning resources after all compiler volumes finish teardown.

    Uninstall calls this after releasing builders and their PVCs. Live claims or
    retained volumes preserve the provisioner; a failed teardown leaves it running.
    The platform namespace and unrelated storage resources are never removed.
    """
    selector = f"{_OWNER_LABEL}={namespace}"
    owned = managed_build_storage_resources(kubectl, namespace)
    if not owned:
        return "Preserve", "no managed source storage provisioner"
    deadline = time.monotonic() + timeout_seconds(timeout)
    # Keep the controller and helper permissions until Delete-policy PVs disappear.
    while True:
        classes = {
            storage_class["metadata"]["name"]
            for storage_class in kubectl.list_cluster_resources(("storageclasses",))
            if storage_class.get("provisioner") == SOURCE_BUILD_PROVISIONER
        }
        classes.add(SOURCE_BUILD_STORAGE_CLASS)
        claims = [
            claim
            for claim in kubectl.list_all_resources(("persistentvolumeclaims",))
            if claim["spec"].get("storageClassName") in classes
        ]
        active = [
            claim for claim in claims if not claim["metadata"].get("deletionTimestamp")
        ]
        if active:
            return "Preserve", "source storage still has PVC consumers"
        volumes = [
            volume
            for volume in kubectl.list_cluster_resources(("persistentvolumes",))
            if volume["spec"].get("storageClassName") in classes
            or volume["metadata"]
            .get("annotations", {})
            .get("pv.kubernetes.io/provisioned-by")
            == SOURCE_BUILD_PROVISIONER
        ]
        if any(
            volume["spec"].get("persistentVolumeReclaimPolicy") != "Delete"
            for volume in volumes
        ):
            return "Preserve", "retained source volumes still need the provisioner"
        if not claims and not volumes:
            break
        if time.monotonic() >= deadline:
            raise DeploymentError(
                "source storage volume teardown did not finish within " + timeout
            )
        time.sleep(1)
    if classes - {SOURCE_BUILD_STORAGE_CLASS}:
        return "Preserve", "another StorageClass uses the source provisioner"
    # Label selection is evaluated by the server, so an unowned replacement is untouched.
    for kinds, scope in (
        (_CLUSTER_KINDS, []),
        (_NAMESPACED_KINDS, ["--namespace", namespace]),
    ):
        kubectl.run(
            [
                "delete",
                ",".join(kinds),
                *scope,
                "--selector",
                selector,
                "--ignore-not-found",
                "--wait=true",
                "--timeout=" + timeout,
            ]
        )
    return "Removed", SOURCE_BUILD_STORAGE_CLASS
