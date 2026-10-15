# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Run cached source builds beside their outputs, transferring only changed inputs."""

from __future__ import annotations

import base64
import io
import json
import os
import re
import shlex
import subprocess
import tarfile
import tempfile
import time
import uuid
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from threading import Lock
from typing import Any, Self

import yaml

from foretoken.kubernetes import Kubectl
from foretoken.manifest import DeploymentError
from foretoken.node_images import (
    SOURCE_BUILD_BINDING_LABEL,
    SOURCE_BUILD_POD_LABEL,
    NodeImageStore,
    image_manifest_digest,
    images_container_spec,
)

_BUILD_POD_LABEL = SOURCE_BUILD_POD_LABEL
_BUILD_BINDING_LABEL = SOURCE_BUILD_BINDING_LABEL
_BUILD_MIRRORS_ANNOTATION = "inference.foretoken.io/source-build-registry-mirrors"


class ImageNotFoundError(DeploymentError):
    """Identify a collected registry artifact that its source producer can rebuild."""


def _image_reference(image: str) -> str:
    """Normalize Docker's shorthand references for node-store lookups."""
    first = image.split("/", 1)[0]
    if "/" not in image or not ("." in first or ":" in first or first == "localhost"):
        image = "docker.io/" + ("library/" if "/" not in image else "") + image
    if ":" not in image.rsplit("/", 1)[-1] and "@" not in image:
        image += ":latest"
    return image


def _pod_ready(pod: dict[str, Any]) -> bool:
    """Return whether a source builder Pod can safely be reused."""
    return pod.get("status", {}).get("phase") == "Running" and any(
        condition.get("type") == "Ready" and condition.get("status") == "True"
        for condition in pod.get("status", {}).get("conditions", [])
    )


def remove_build_pods(
    kubectl: Kubectl,
    timeout: str,
    *,
    binding: str = "",
    preserve_ready: bool = False,
) -> None:
    """Retire abandoned builders, or all builders during source uninstall."""
    selector = _BUILD_POD_LABEL + "=true"
    if binding:
        selector += "," + _BUILD_BINDING_LABEL + "=" + binding
    if not preserve_ready:
        kubectl.run(
            [
                "delete",
                "pods",
                "--all-namespaces",
                "--selector",
                selector,
                "--ignore-not-found",
                "--wait=true",
                "--timeout=" + timeout,
            ]
        )
        return
    for pod in kubectl.list_all_resources(("pods",), label_selector=selector):
        # Retire obsolete cache-mounted publishers even when their compiler is healthy.
        if _pod_ready(pod) and not any(
            container["name"] == "publisher" for container in pod["spec"]["containers"]
        ):
            continue
        metadata = pod.get("metadata", {})
        name, namespace = metadata.get("name"), metadata.get("namespace")
        if name and namespace:
            kubectl.run(
                [
                    "delete",
                    "pod",
                    name,
                    "--namespace",
                    namespace,
                    "--ignore-not-found",
                    "--wait=true",
                    "--timeout=" + timeout,
                ]
            )


def find_build_cache(
    kubectl: Kubectl, namespace: str, binding: str, node: str, mount: str
) -> str | None:
    """Find this binding's existing compiler volume on the requested node and mount."""
    selector = f"{_BUILD_POD_LABEL}=true,{_BUILD_BINDING_LABEL}={binding}"
    for pod in kubectl.list_resources(("pods",), namespace, label_selector=selector):
        if pod["spec"].get("nodeName") != node:
            continue
        builders = [
            container
            for container in pod["spec"]["containers"]
            if container["name"] == "builder"
        ]
        if not any(
            volume["name"] == "cache" and volume["mountPath"] == mount
            for builder in builders
            for volume in builder.get("volumeMounts", [])
        ):
            continue
        return next(
            volume["persistentVolumeClaim"]["claimName"]
            for volume in pod["spec"]["volumes"]
            if volume["name"] == "cache"
        )
    return None


def registry_credentials(images: list[str]) -> dict[str, Any]:
    """Resolve workstation login helpers only for registries used by this build."""
    path = (
        Path(os.environ.get("DOCKER_CONFIG", str(Path.home() / ".docker")))
        / "config.json"
    )
    if not path.is_file():
        return {}
    configuration = json.loads(path.read_text())
    hosts = {image.split("/", 1)[0] for image in images if image}
    aliases = {"docker.io": "https://index.docker.io/v1/"}
    auths = {}
    for host in hosts:
        key = aliases.get(host, host)
        entries = configuration.get("auths", {})
        helper = configuration.get("credHelpers", {}).get(host)
        if not helper and (key in entries or host in entries):
            helper = configuration.get("credsStore")
        if helper:
            result = subprocess.run(
                ["docker-credential-" + helper, "get"],
                input=key,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.returncode:
                raise DeploymentError(f"could not read login credentials for {host}")
            credentials = json.loads(result.stdout)
            if credentials["Username"] == "<token>":
                auths[host] = {"identitytoken": credentials["Secret"]}
            else:
                token = f"{credentials['Username']}:{credentials['Secret']}".encode()
                auths[host] = {"auth": base64.b64encode(token).decode()}
        elif key in entries or host in entries:
            auths[host] = entries.get(key, entries.get(host))
    return {"auths": auths} if auths else {}


def _cache_gc_limits(quantity: str) -> tuple[str, str, str]:
    """Apply the pinned BuildKit defaults to its PVC allocation instead of a shared host disk."""
    match = re.fullmatch(
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([KMGTPE]i|[numkKMGTPE])?",
        quantity,
    )
    if match is None:
        raise DeploymentError(f"invalid compiler volume capacity: {quantity}")
    amount, suffix = match.groups()
    suffix = suffix or ""
    if suffix.endswith("i"):
        multiplier = Decimal(1024) ** ("KMGTPE".index(suffix[0]) + 1)
    else:
        multiplier = (
            Decimal(10)
            ** {
                "n": -9,
                "u": -6,
                "m": -3,
                "": 0,
                "k": 3,
                "K": 3,
                "M": 6,
                "G": 9,
                "T": 12,
                "P": 15,
                "E": 18,
            }[suffix]
        )
    capacity = int(Decimal(amount) * multiplier)
    # BuildKit 0.33 reserves 10% (up to 10 GB), keeps 20% free, and uses at most
    # 80% (up to 100 GB). Explicit image configuration remains authoritative.
    return (
        str(min(capacity // 10, 10_000_000_000)),
        str(capacity // 5),
        str(min(capacity * 4 // 5, 100_000_000_000)),
    )


class ClusterBuilder(AbstractContextManager):
    """Own one BuildKit Pod while its source workspace and build cache survive on a volume."""

    def __init__(
        self,
        kubectl: Kubectl,
        namespace: str,
        claim: str,
        mount: str,
        image: str,
        binding: str,
        timeout: str,
        *,
        tools_image: str,
        node: str = "",
        containerd_socket: str = "",
        pull_secrets: tuple[str, ...] = (),
        credentials: dict[str, Any] | None = None,
        registry_mirrors: dict[str, list[str]] | None = None,
    ) -> None:
        self.kubectl = kubectl
        self.namespace = namespace
        self.claim = claim
        self.mount = mount.rstrip("/")
        self.image = image
        self.tools_image = tools_image
        self.binding = binding
        self.timeout = timeout
        self.node = node
        self.containerd_socket = containerd_socket
        self.pull_secrets = pull_secrets
        self.credentials = credentials or {}
        self.registry_mirrors = registry_mirrors or {}
        self.name = "foretoken-build-" + uuid.uuid4().hex[:12]
        self.root = f"{self.mount}/build/{binding}"
        self.workspace = f"{self.root}/workspace"
        self._created = False
        self._image_lock = Lock()
        self._generated_layouts: dict[str, dict[str, str]] = {}
        self._used_images: set[str] = set()
        self._built_images: set[str] = set()
        self._resolved_images: dict[str, str] = {}

    def _reuse_or_retire_pods(self) -> dict[str, Any] | None:
        """Select a compatible daemon and retire other builders sharing its compiler cache."""
        selector = f"{_BUILD_POD_LABEL}=true,{_BUILD_BINDING_LABEL}={self.binding}"
        occupants = []
        candidates = []
        for pod in self.kubectl.list_resources(
            ("pods",), self.namespace, label_selector=selector
        ):
            if not any(
                volume["name"] == "cache"
                and volume.get("persistentVolumeClaim", {}).get("claimName")
                == self.claim
                for volume in pod["spec"].get("volumes", [])
            ):
                continue
            occupants.append(pod)
            if not _pod_ready(pod) or pod.get("metadata", {}).get("deletionTimestamp"):
                continue
            if self.node and pod.get("spec", {}).get("nodeName") != self.node:
                continue
            if pod["metadata"].get("annotations", {}).get(
                _BUILD_MIRRORS_ANNOTATION, "{}"
            ) != json.dumps(self.registry_mirrors, sort_keys=True):
                continue
            containers = pod.get("spec", {}).get("containers", [])
            builder = next(
                (
                    container
                    for container in containers
                    if container.get("name") == "builder"
                ),
                None,
            )
            if builder is None or builder.get("image") != self.image:
                continue
            images = next(
                (
                    container
                    for container in containers
                    if container.get("name") == "images"
                ),
                None,
            )
            # File-only exports can reuse a daemon with an idle image-import helper.
            if self.containerd_socket and (
                images is None or images.get("image") != self.tools_image
            ):
                continue
            auth = next(
                (
                    volume.get("secret")
                    for volume in pod["spec"].get("volumes", [])
                    if volume["name"] == "registry-auth"
                ),
                None,
            )
            if bool(auth) != bool(self.credentials):
                continue
            if auth is not None:
                secret = self.kubectl.get_if_exists(
                    "secret", auth["secretName"], self.namespace
                )
                # A new Pod mounts current credentials before its first build starts.
                if secret is None or json.loads(
                    base64.b64decode(secret["data"][".dockerconfigjson"])
                ) != self.credentials:
                    continue
            candidates.append(pod)
        reusable = min(
            candidates,
            key=lambda pod: pod.get("metadata", {}).get("creationTimestamp", ""),
            default=None,
        )
        # The caller owns this binding's operation lock. Stop its previous daemon
        # before changing image or placement: the PVC still holds its root lock.
        for pod in occupants:
            if pod is reusable:
                continue
            self.kubectl.run(
                [
                    "delete",
                    "pod",
                    pod["metadata"]["name"],
                    "--namespace",
                    self.namespace,
                    "--ignore-not-found",
                    "--wait=true",
                    "--timeout=" + self.timeout,
                ]
            )
        return reusable

    def __enter__(self) -> Self:
        """Reuse or start the compiler daemon on the cache's node."""
        reusable = self._reuse_or_retire_pods()
        if reusable is not None:
            self.name = reusable["metadata"]["name"]
            print(f"Reusing cluster builder {self.namespace}/{self.name}", flush=True)
            self.run(
                [
                    "sh",
                    "-ec",
                    'rm -rf -- "$1/transfers" "$1/output" "$1/results"; mkdir -p "$1/results"',
                    "prepare",
                    self.root,
                ]
            )
            return self
        image = self.image
        pvc = self.kubectl.get("pvc", self.claim, self.namespace)
        capacity = (
            pvc.get("status", {})
            .get("capacity", {})
            .get("storage", pvc["spec"]["resources"]["requests"]["storage"])
        )
        gc_limits = _cache_gc_limits(capacity)
        # Keep canonical image names so BuildKit can fall back from a mirror to the origin.
        # An image-supplied daemon configuration remains authoritative.
        mirrors = "".join(
            f"\n[registry.{json.dumps(host)}]\nmirrors = {json.dumps(endpoints)}\n"
            for host, endpoints in sorted(self.registry_mirrors.items())
        )
        spec: dict[str, Any] = {
            "restartPolicy": "Never",
            "hostNetwork": True,
            "dnsPolicy": "Default",
            "automountServiceAccountToken": False,
            "tolerations": [
                {"key": key, "operator": "Exists", "effect": "NoSchedule"}
                for key in (
                    "node-role.kubernetes.io/control-plane",
                    "node-role.kubernetes.io/master",
                )
            ],
            "imagePullSecrets": [{"name": name} for name in self.pull_secrets],
            "volumes": [
                {"name": "cache", "persistentVolumeClaim": {"claimName": self.claim}}
            ],
            "initContainers": [
                {
                    "name": "workspace",
                    "image": image,
                    "command": [
                        "sh",
                        "-ec",
                        """mount="$(dirname "$(dirname "$1")")"
mkdir -p "$mount" "$1"
chown 1000:1000 "$mount" "$mount/build" "$(dirname "$1")" "$1"
chmod 2775 "$mount" "$mount/build" "$(dirname "$1")" "$1"
configuration="${XDG_CONFIG_HOME:-$HOME/.config}/buildkit/buildkitd.toml"
if test -f "$configuration"; then
    cp "$configuration" "$1/buildkit.toml"
else
    printf "[worker.oci]\\nreservedSpace = %s\\nminFreeSpace = %s\\nmaxUsedSpace = %s\\n" \\
        "$2" "$3" "$4" > "$1/buildkit.toml"
    printf "%s" "$5" >> "$1/buildkit.toml"
fi
chown 1000:1000 "$1/buildkit.toml"
chmod 600 "$1/buildkit.toml"
""",
                        "prepare",
                        self.root,
                        *gc_limits,
                        mirrors,
                    ],
                    "securityContext": {"runAsUser": 0},
                    "volumeMounts": [{"name": "cache", "mountPath": self.mount}],
                }
            ],
        }
        container: dict[str, Any] = {
            "name": "builder",
            "image": image,
            "env": [{"name": "NVIDIA_VISIBLE_DEVICES", "value": "void"}],
            "args": [
                "--root",
                f"{self.root}/buildkit",
                "--config",
                f"{self.root}/buildkit.toml",
            ],
            "volumeMounts": [{"name": "cache", "mountPath": self.mount}],
            "readinessProbe": {
                "exec": {"command": ["buildctl", "debug", "workers"]},
                "periodSeconds": 2,
            },
        }
        container["args"].append("--oci-worker-no-process-sandbox")
        container["securityContext"] = {
            "runAsUser": 1000,
            "runAsGroup": 1000,
            "seccompProfile": {"type": "Unconfined"},
            "appArmorProfile": {"type": "Unconfined"},
        }
        if self.node:
            spec["affinity"] = {
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
                        ]
                    }
                }
            }
        if self.credentials:
            spec["imagePullSecrets"].append({"name": self.name})
            spec["volumes"].append(
                {
                    "name": "registry-auth",
                    "secret": {
                        "secretName": self.name,
                        "items": [{"key": ".dockerconfigjson", "path": "config.json"}],
                    },
                }
            )
            container["volumeMounts"].append(
                {
                    "name": "registry-auth",
                    "mountPath": "/registry-auth",
                    "readOnly": True,
                }
            )
            container["env"].append(
                {"name": "DOCKER_CONFIG", "value": "/registry-auth"}
            )
        spec["containers"] = [container]
        if self.containerd_socket:
            # Only local kind/k3d installation uses node image import. The compiler
            # never receives the runtime socket; archives remain on the cluster volume.
            # GNU tar preserves PAX sizes for OCI layer blobs larger than 8 GiB.
            images, volumes = images_container_spec(
                self.tools_image, self.containerd_socket
            )
            images["volumeMounts"].insert(0, {"name": "cache", "mountPath": self.mount})
            spec["volumes"] += volumes
            spec["containers"].append(images)
        pod = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "annotations": {
                    _BUILD_MIRRORS_ANNOTATION: json.dumps(
                        self.registry_mirrors, sort_keys=True
                    ),
                },
                "labels": {
                    _BUILD_POD_LABEL: "true",
                    _BUILD_BINDING_LABEL: self.binding,
                },
            },
            "spec": spec,
        }
        print(f"Preparing cluster builder {self.namespace}/{self.name}", flush=True)
        try:
            created = self.kubectl.run(
                ["create", "-f", "-", "-o", "json"], input_text=yaml.safe_dump(pod)
            )
            self._created = True
            pod_uid = json.loads(created.stdout)["metadata"]["uid"]
            if self.credentials:
                self.kubectl.run(
                    ["create", "-f", "-"],
                    input_text=yaml.safe_dump(
                        {
                            "apiVersion": "v1",
                            "kind": "Secret",
                            "type": "kubernetes.io/dockerconfigjson",
                            "metadata": {
                                "name": self.name,
                                "namespace": self.namespace,
                                "ownerReferences": [
                                    {
                                        "apiVersion": "v1",
                                        "kind": "Pod",
                                        "name": self.name,
                                        "uid": pod_uid,
                                    }
                                ],
                            },
                            "data": {
                                ".dockerconfigjson": base64.b64encode(
                                    json.dumps(self.credentials).encode()
                                ).decode()
                            },
                        }
                    ),
                )
            self.kubectl.run(
                [
                    "wait",
                    "pod/" + self.name,
                    "-n",
                    self.namespace,
                    "--for=condition=Ready",
                    "--timeout=" + self.timeout,
                ]
            )
            self.run(
                [
                    "sh",
                    "-ec",
                    'rm -rf -- "$1/transfers" "$1/output" "$1/results"; mkdir -p "$1/results"',
                    "prepare",
                    self.root,
                ]
            )
        except BaseException as error:
            self.__exit__(type(error), error, error.__traceback__)
            raise
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        """Retain successful builders and clean transient or failed build state."""
        if exc_type is not None:
            # A failed daemon may no longer accept exec. Retire a new Pod directly;
            # the next successful entry removes partial exports from a reused cache.
            if self._created:
                self.kubectl.run(
                    [
                        "delete",
                        "pod",
                        self.name,
                        "-n",
                        self.namespace,
                        "--ignore-not-found",
                        "--wait=true",
                        "--timeout=" + self.timeout,
                    ]
                )
                self._created = False
            return
        self.run(["rm", "-rf", "--", self.root + "/results", self.root + "/transfers"])
        if self._used_images:
            path = self.root + "/images.json"
            layouts = self.read_json(path)
            stale = [
                value["path"]
                for image, value in layouts.items()
                if image not in self._used_images
            ]
            retained = {
                image: value
                for image, value in layouts.items()
                if image in self._used_images
            }
            encoded = shlex.quote(json.dumps(retained))
            self.run(
                [
                    "sh",
                    "-ec",
                    f'printf %s {encoded} > "$1.next"; mv "$1.next" "$1"',
                    "save",
                    path,
                ]
            )
            if stale:
                self.run(["rm", "-rf", "--", *stale])

    def command(self, args: list[str], *, container: str = "builder") -> list[str]:
        """Address the build Pod for both streamed input and ordinary commands."""
        return self.kubectl.command(
            [
                "exec",
                "-i",
                "-n",
                self.namespace,
                self.name,
                "-c",
                container,
                "--",
                *args,
            ]
        )

    def run(
        self,
        args: list[str],
        *,
        capture: bool = False,
        container: str = "builder",
        input_text: str | None = None,
    ) -> str:
        """Execute a build stage, preserving live compiler and daemon diagnostics on failure."""
        started = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        result = subprocess.run(
            self.command(args, container=container),
            check=False,
            text=True,
            capture_output=capture,
            input=input_text,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout or "").strip()
            if container == "builder" and args[0] == "buildctl":
                # Frontend startup failures can reach buildctl as only an exit code.
                # Preserve the daemon's cause before the context retires a failed Pod.
                logs = subprocess.run(
                    self.kubectl.command([
                        "logs", "-n", self.namespace, self.name, "-c", "builder",
                        "--since-time=" + started, "--timestamps",
                        "--request-timeout=" + self.timeout,
                    ]),
                    text=True, capture_output=True, check=False,
                )
                if logs.returncode == 0 and logs.stdout.strip():
                    print(logs.stdout, flush=True)
                    if any(
                        "session key" in line and "disk quota exceeded" in line
                        for line in logs.stdout.splitlines()
                    ):
                        detail = (
                            "the host kernel keyring quota for the builder's UID is exhausted; "
                            "inspect /proc/key-users and kernel.keys.maxkeys/maxbytes on the host, "
                            "then identify retained keyring references or adjust host key capacity"
                        )
                elif logs.returncode:
                    print(f"Builder logs unavailable: {logs.stderr.strip()}", flush=True)
            raise DeploymentError(
                f"cluster build failed in {self.namespace}/{self.name}"
                + (f" on node {self.node}" if self.node else "")
                + f": {detail or result.returncode}"
            )
        return result.stdout if capture else ""

    def read_json(self, path: str, *, container: str = "builder") -> dict[str, Any]:
        """Read optional operation metadata without hiding malformed or unreadable state."""
        text = self.run(
            [
                "sh",
                "-ec",
                'if test -f "$1"; then cat "$1"; else printf "{}"; fi',
                "read",
                path,
            ],
            capture=True,
            container=container,
        )
        return json.loads(text)

    def sync(self, files: dict[str, Path], versions: dict[str, str]) -> None:
        """Apply a path-level delta; an interrupted upload is replaced completely on retry."""
        started = time.monotonic()
        marker = self.root + "/inputs.json"
        previous = self.read_json(marker)
        changed = [name for name in files if previous.get(name) != versions[name]]
        removed = sorted(previous.keys() - versions.keys())
        if not changed and not removed:
            print("Source transfer: reused unchanged workspace", flush=True)
            return
        # The receipt is installed last. Without it a retry starts from an empty managed
        # workspace, rather than accepting files left by a partially received archive.
        reset = not previous
        script = """set -eu
root=$1; workspace=$2; reset=$3; incoming="$root/incoming"
rm -rf "$incoming"; mkdir -p "$incoming"
tar --no-same-owner -xzf - -C "$incoming"
rm -f "$root/inputs.json"
if test "$reset" = true; then rm -rf "$workspace"; fi
mkdir -p "$workspace"; cd "$workspace"
xargs -0 -r rm -f -- < "$incoming/.foretoken-removed"
find . -mindepth 1 -depth -type d -empty -delete
rm "$incoming/.foretoken-removed"
mv "$incoming/.foretoken-inputs" "$root/inputs.next"
# Cargo and Ninja must observe changed bytes even when client timestamps were restored.
find "$incoming" -type f -exec touch {} +
cp -pRf "$incoming/." "$workspace/"
mv "$root/inputs.next" "$root/inputs.json"
rm -rf "$incoming"
"""
        with tempfile.TemporaryFile() as stream:
            with tarfile.open(fileobj=stream, mode="w:gz") as archive:
                for name in changed:
                    archive.add(files[name], arcname=name, recursive=False)
                for name, data in (
                    (".foretoken-removed", b"\0".join(p.encode() for p in removed)),
                    (".foretoken-inputs", json.dumps(versions).encode()),
                ):
                    entry = tarfile.TarInfo(name)
                    entry.size = len(data)
                    entry.mode = 0o644
                    archive.addfile(entry, io.BytesIO(data))
            print(
                f"Source transfer: {len(changed)} changed files, {len(removed)} removed files, {stream.tell()} compressed bytes",
                flush=True,
            )
            stream.seek(0)
            result = subprocess.run(
                self.command(
                    [
                        "sh",
                        "-c",
                        script,
                        "sync",
                        self.root,
                        self.workspace,
                        str(reset).lower(),
                    ]
                ),
                stdin=stream,
                check=False,
            )
        if result.returncode:
            raise DeploymentError("source delta upload failed")
        print(
            f"Source transfer completed in {time.monotonic() - started:.1f}s",
            flush=True,
        )

    def export_application(
        self,
        component: str,
        destination: str,
        arguments: dict[str, str],
        parts: list[str] | None = None,
    ) -> None:
        """Export selected first-party application parts; callers assemble engine files separately."""
        if parts is None or "rust" in parts:
            dockerfile = (
                "control-plane/Dockerfile" if component == "control-plane"
                else f"data-plane/{component}/Dockerfile"
            )
            # Runtime stages are outside the application export graph. Do not
            # materialize SDK images merely to supply their unused Dockerfile ARGs.
            arguments = {
                key: value for key, value in arguments.items()
                if not key.endswith("_IMAGE")
                or key in {"RUST_BUILDER_IMAGE", "GO_BUILDER_IMAGE", "BUILDKIT_SYNTAX_IMAGE"}
            }
            if component == "model-server":
                arguments["INFERENCE_ENGINE_IMAGE"] = "scratch"
            self.build(dockerfile, target="source-export", destination=destination, arguments=arguments)
            return
        script = 'rm -rf "$1"; mkdir -p "$1"'
        if "python" in parts:
            script += (
                '; mkdir "$1/python"; '
                'if test -d "$2"; then cp -pR "$2/." "$1/python/"; fi'
            )
        self.run([
            "sh", "-ec", script, "export", destination,
            self.workspace + "/data-plane/model-server/python",
        ])

    def _containerd(self) -> list[str]:
        """Address the local development node's image store through its own client."""
        return NodeImageStore(
            self.kubectl, self.namespace, self.name, self.binding
        ).containerd()

    def resolve_image(self, image: str) -> str:
        """Resolve a build dependency through the same node store or registry used by BuildKit."""
        if image in self._resolved_images:
            return self._resolved_images[image]
        name = _image_reference(image)
        if name in self._generated_layouts:
            digest = self._generated_layouts[name]["digest"]
        elif self.containerd_socket:
            digest = NodeImageStore(
                self.kubectl, self.namespace, self.name, self.binding
            ).image_digest(name)
        else:
            digest = None
        if digest is None:
            # A FROM-only solve uses BuildKit's registry credentials, mirrors and
            # platform selection without running a container or adding image layers.
            dockerfile = ".foretoken-resolve/Dockerfile"
            self.run([
                "sh", "-ec",
                'mkdir -p "$1/.foretoken-resolve"; printf \'ARG BASE_IMAGE\\nFROM ${BASE_IMAGE}\\n\' > "$1/.foretoken-resolve/Dockerfile"',
                "resolve", self.workspace,
            ])
            try:
                metadata = self.build(
                    dockerfile, image="foretoken-resolve:" + uuid.uuid4().hex,
                    arguments={"BASE_IMAGE": image}, capture=True, metadata_only=True,
                )
            except DeploymentError as error:
                message = str(error)
                if "failed to resolve source metadata" in message and (
                    f"{image}: not found" in message or "404 Not Found" in message
                ):
                    raise ImageNotFoundError(message) from error
                raise
            digest = metadata["containerimage.digest"]
        self._resolved_images[image] = digest
        return digest

    def image_matches(self, image: str, digest: str) -> bool:
        """Verify a retained environment against its producer's OCI descriptor on this node."""
        if self.containerd_socket:
            return self._node_image_matches(image, digest)
        return self.resolve_image(image) == digest

    def _node_images(self) -> dict[str, str]:
        """Read node references for existing local build-context reuse."""
        return NodeImageStore(
            self.kubectl, self.namespace, self.name, self.binding
        ).images()

    def _node_image_matches(self, image: str, digest: str) -> bool:
        """Compare a selected node image with BuildKit output without exporting layers."""
        return NodeImageStore(
            self.kubectl, self.namespace, self.name, self.binding
        ).matches(image, digest)

    def _save_layout(self, image: str, layout: str, digest: str) -> None:
        """Retain the cluster-local OCI layout corresponding to an imported image reference."""
        path = self.root + "/images.json"
        layouts = self.read_json(path)
        previous = layouts.get(image)
        layouts[image] = {
            "path": layout,
            "digest": digest,
            "nodeDigest": self._node_images()[image],
        }
        encoded = shlex.quote(json.dumps(layouts))
        self.run(
            [
                "sh",
                "-ec",
                f'printf %s {encoded} > "$1.next"; mv "$1.next" "$1"',
                "save",
                path,
            ]
        )
        if previous and previous["path"] != layout:
            self.run(["rm", "-rf", "--", previous["path"]])

    def _local_image(self, image: str) -> dict[str, str] | None:
        """Expose built OCI outputs or existing node images as registry-free BuildKit contexts."""
        if not self.containerd_socket or image == "scratch":
            return None
        name = _image_reference(image)
        if name in self._generated_layouts:
            self._used_images.add(name)
            return self._generated_layouts[name]
        images = self._node_images()
        if name not in images:
            return None
        self._used_images.add(name)
        cached = self.read_json(self.root + "/images.json").get(name)
        if cached and cached["nodeDigest"] == images[name]:
            return cached
        layout = self.root + "/images/" + uuid.uuid4().hex
        self.run(["mkdir", "-p", layout])
        machine = self.run(["uname", "-m"], capture=True).strip()
        platform = "linux/" + {"x86_64": "amd64", "aarch64": "arm64"}[machine]
        self.run(
            [
                *self._containerd(),
                "images",
                "export",
                "--skip-manifest-json",
                "--platform",
                platform,
                layout + "/image.tar",
                name,
            ],
            container="images",
        )
        self.run(
            [
                "sh",
                "-ec",
                'tar --no-same-owner -xf "$1/image.tar" -C "$1"; rm "$1/image.tar"',
                "extract",
                layout,
            ],
            container="images",
        )
        digest = self.read_json(layout + "/index.json")["manifests"][0]["digest"]
        self._save_layout(name, layout, digest)
        return {"path": layout, "digest": digest, "nodeDigest": images[name]}

    def _context_digest(self, layout: dict[str, str]) -> str:
        """Resolve a single-image index for BuildKit without changing export identities."""
        return image_manifest_digest(
            layout["digest"],
            lambda digest: self.read_json(layout["path"] + "/blobs/" + digest.replace(":", "/", 1)),
        )

    def build(
        self,
        dockerfile: str,
        *,
        target: str = "",
        destination: str = "",
        image: str = "",
        push: bool = False,
        arguments: dict[str, str] | None = None,
        capture: bool = False,
        metadata_only: bool = False,
    ) -> dict[str, Any]:
        """Build files or complete images, retaining local OCI outputs until delivery.

        Dependency resolution uses metadata_only to inspect a base without exporting its layers.
        """
        metadata = self.root + "/results/" + uuid.uuid4().hex + ".json"
        args = [
            "buildctl",
            "build",
            "--frontend",
            "dockerfile.v0",
            "--local",
            "context=" + self.workspace,
            "--local",
            "dockerfile=" + self.workspace,
            "--opt",
            "filename=" + dockerfile,
            "--metadata-file",
            metadata,
            "--progress",
            "plain",
        ]
        if target:
            args += ["--opt", "target=" + target]
        syntax_image = (arguments or {}).get("BUILDKIT_SYNTAX_IMAGE")
        if syntax_image:
            source = self.workspace + "/" + dockerfile
            generated = (
                f"{self.workspace}/.foretoken-build/{uuid.uuid4().hex}/Dockerfile"
            )
            # BuildKit resolves Dockerfile-specific exclusions from the generated filename.
            self.run(
                [
                    "sh",
                    "-ec",
                    (
                        'mkdir -p "$(dirname "$3")"; first=$(head -n 1 "$2"); '
                        'if case "$first" in "# syntax="*) true;; *) false;; esac; then '
                        'tail -n +2 "$2" > "$3"; else cp "$2" "$3"; fi; '
                        'if test -f "$2.dockerignore"; then '
                        'cp "$2.dockerignore" "$3.dockerignore"; fi'
                    ),
                    "rewrite",
                    syntax_image,
                    source,
                    generated,
                ],
            )
            dockerfile = generated.removeprefix(self.workspace + "/")
            args[args.index("--opt") + 1] = "filename=" + dockerfile
        for key, value in (arguments or {}).items():
            local = None
            if key.endswith("_IMAGE"):
                # Local contexts share OCI exports and their index. Resolve them
                # atomically; independent buildctl solves run outside this lock.
                with self._image_lock:
                    local = self._local_image(value)
            if local:
                digest = self._context_digest(local)
                alias = "foretoken-local-" + key.lower().replace("_", "-")
                args += [
                    "--oci-layout",
                    alias + "=" + local["path"],
                    "--opt",
                    f"context:{alias}=oci-layout://{alias}@{digest}",
                ]
                value = alias
            args += ["--opt", f"build-arg:{key}={value}"]
        layout = ""
        if destination:
            # BuildKit mirrors each owned export directory so retries cannot revive removed files.
            output = "type=local,mode=delete,dest=" + destination
        elif metadata_only:
            output = f"type=image,name={image},oci-mediatypes=true,store=false,push=false"
        elif self.containerd_socket:
            # An exported layout owns the result independently of BuildKit's cache.
            # Replaying a completed solve for delivery can rebuild evicted dependency layers.
            layout = self.root + "/transfers/" + uuid.uuid4().hex
            output = f"type=oci,name={image},oci-mediatypes=true,dest={layout},tar=false"
        else:
            output = f"type=image,name={image},push={str(push).lower()}"
        started = time.monotonic()
        self.run([*args, "--output", output], capture=capture)
        result = self.read_json(metadata)
        target_name = target or "default"
        output_name = destination or image or "files"
        print(
            f"Build completed: {dockerfile} target={target_name} output={output_name} "
            f"in {time.monotonic() - started:.1f}s",
            flush=True,
        )
        if layout:
            self._generated_layouts[_image_reference(image)] = {
                "path": layout, "digest": result["containerimage.digest"],
            }
        return result

    def import_image(self, image: str, reference: str) -> None:
        """Deliver a selected OCI output after source builds, reusing an identical node image."""
        image = _image_reference(image)
        layout = self._generated_layouts[image]
        digest = layout["digest"]
        if self._node_image_matches(reference, digest):
            print(f"Reusing unchanged node image {reference}", flush=True)
            NodeImageStore(
                self.kubectl, self.namespace, self.name, self.binding
            ).pin_owned(reference)
        else:
            NodeImageStore(
                self.kubectl, self.namespace, self.name, self.binding
            ).import_layout(layout["path"], reference)
            # Retire only references created by this operation after delivery.
            self._built_images.update((image, reference))
        if image in self._used_images:
            # A generated environment consumed by this build is also the next
            # iteration's input. Retain its immutable OCI files without copying
            # layer bytes or invalidating in-flight commands' original paths.
            cached = self.root + "/images/" + uuid.uuid4().hex
            self.run(["mkdir", "-p", self.root + "/images"])
            self.run(["cp", "-al", layout["path"], cached])
            self._save_layout(reference, cached, digest)
            self._used_images.add(reference)

    def discard_unselected_images(self, retained: set[str]) -> None:
        """Remove only this build's unselected local references after every node has been compared."""
        if self.containerd_socket:
            NodeImageStore(
                self.kubectl, self.namespace, self.name, self.binding
            ).remove_owned(self._built_images - retained)
