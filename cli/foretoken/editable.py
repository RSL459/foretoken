# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Prepare source-installed runtime updates without rebuilding their environment images."""

from __future__ import annotations

import copy
import filecmp
import json
import time
import uuid
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

from foretoken.application_files import ApplicationFiles
from foretoken.arguments import InstallCommand
from foretoken.cluster_build import (
    ClusterBuilder,
    find_build_cache,
    registry_credentials,
)
from foretoken.kubernetes import Kubectl, timeout_seconds
from foretoken.manifest import (
    DeploymentError,
    ForetokenDeployment,
    ResourceRef,
    parse_deployment,
)
from foretoken.platform import PlatformLifecycle
from foretoken.platform.config import default_platform_config
from foretoken.platform.helm import Helm
from foretoken.source import (
    _INSTALL_SOURCE,
    SOURCE_REVISION,
    _has_server_binding,
    _inputs,
    _local_candidates,
    _runtime_settings,
    _snapshot,
    _state_directory,
    _write_json,
    ensure_build_cache,
    image_tools_image,
    local_build_nodes,
    pinned_rust_revision,
    snapshot_versions,
    validate_build_inputs,
)
from foretoken.storage import DirectoryVolumes

_COMPONENTS = {"ModelService": "model-server", "FrontendService": "frontend"}


class EditableDeployment:
    """Own local source comparison, candidate preparation and target-service activation."""

    def __init__(
        self, kubectl: Kubectl, directory: Path, state: dict[str, Any]
    ) -> None:
        self.kubectl = kubectl
        self.directory = directory
        self.state = state
        self.root = Path(state["root"])
        self.selected: dict[tuple[str, str, str], str] = {}

    @classmethod
    def discover(cls, kubectl: Kubectl) -> EditableDeployment | None:
        """Enable source updates only for a platform installed explicitly from source."""
        if not _has_server_binding(kubectl):
            return None
        platforms = kubectl.list_all_resources(
            ("deployment.apps",),
            label_selector="app.kubernetes.io/name=foretoken-control-plane",
        )
        source = [
            p
            for p in platforms
            if p["metadata"].get("annotations", {}).get(_INSTALL_SOURCE) == "source"
        ]
        if not source:
            return None
        directory = _state_directory(kubectl)
        path = directory / "install.json"
        if not path.is_file():
            raise DeploymentError(
                "source checkout is not associated with this workstation; run `foretoken install -e .` from that checkout's root"
            )
        state = json.loads(path.read_text())
        if (
            len(source) != 1
            or state.get("platform_uid") != source[0]["metadata"]["uid"]
            or state["runtime"] != _runtime_settings(source[0])
        ):
            raise DeploymentError(
                "source installation changed; run `foretoken install -e .` from the intended checkout's root"
            )
        if not Path(state["root"]).is_dir():
            raise DeploymentError(
                f"source checkout is unavailable: {state['root']}; run `foretoken install -e .` from that checkout's root"
            )
        return cls(kubectl, directory, state)

    def prepare(self, timeout: str) -> None:
        """Prepare changed runtime artifacts and retire candidates not retained by committed state."""
        with _local_candidates(self.directory):
            self._prepare(timeout)

    def _prepare(self, timeout: str) -> None:
        """Capture a runtime update or reuse installation for build-environment changes."""

        if not self.state.get("build") or self.state["build"]["arguments"].get(
            "VLLM_REVISION"
        ) != pinned_rust_revision(self.root):
            self._rebuild(timeout)
            return
        engines = self.state.get("engines", {})
        current = _inputs(self.root, engines)
        old = self.directory / self.state["inputs"]
        previous = {
            str(p.relative_to(old))
            for p in old.rglob("*")
            if p.is_file()
            and str(p.relative_to(old))
            not in {"engine/manifest.json", "engine/deleted.json"}
        }
        changed = {
            name
            for name in previous | current.keys()
            if name not in previous
            or name not in current
            or not filecmp.cmp(old / name, current[name], shallow=False)
            or (old / name).stat().st_mode != current[name].stat().st_mode
        }
        if not changed:
            print("Source code unchanged; reusing runtime artifacts", flush=True)
            return
        components: set[str] = set()
        compile_components: set[str] = set()
        rebuild = False
        for name in changed:
            if name.startswith("engine/"):
                if Path(name).suffix in {".md", ".png", ".svg"}:
                    continue
                parts = Path(name).parts
                native_source = (
                    "vllm-metax"
                    if self.state["build"]["backend"] == "metax"
                    else "vllm"
                )
                if parts[1] == native_source and (
                    parts[2] in {"csrc", "cmake", "CMakeLists.txt"}
                    or Path(name).suffix
                    in {".cu", ".cuh", ".cpp", ".cc", ".c", ".h", ".hpp", ".cmake"}
                ):
                    self.state["build"]["engine_native"] = True
                if len(parts) > 2 and (
                    parts[2]
                    in {
                        "requirements",
                        "pyproject.toml",
                        "setup.py",
                        "setup.cfg",
                        "Dockerfile",
                    }
                ):
                    rebuild = True
                else:
                    components.add("model-server")
            elif name.startswith("control-plane/") and Path(name).name != "Dockerfile":
                components.add("control-plane")
                compile_components.add("control-plane")
            elif name == "data-plane/artifacts/src/source.rs":
                rebuild = True
            elif name.startswith("data-plane/model-server/python/") and name.endswith(
                ".py"
            ):
                components.add("model-server")
            elif name.startswith("data-plane/") and name.endswith(".rs"):
                targets = (
                    {"frontend"}
                    if name.startswith("data-plane/frontend/")
                    else {"model-server"}
                    if name.startswith("data-plane/model-server/")
                    else {"frontend", "model-server"}
                )
                components.update(targets)
                compile_components.update(targets)
            else:
                rebuild = True
        if rebuild:
            print(
                "Build environment or platform sources changed; updating source installation",
                flush=True,
            )
            self._rebuild(timeout)
            return
        snapshot = self.directory / ("inputs-" + str(uuid.uuid4()))
        _snapshot(
            current,
            snapshot,
            engines,
            previous=old,
            unchanged=set(current).difference(changed),
        )
        validate_build_inputs(self.root, snapshot, engines)
        self.state["build"]["versions"] = snapshot_versions(
            snapshot, old, self.state["build"]["versions"], changed
        )
        bundles = dict(self.state["bundles"])
        for component in components:
            prior = bundles.get(component, {})
            bundles[component] = {
                "revision": str(uuid.uuid4()),
                "compile": component in compile_components
                or prior.get("compile", False),
            }
        self.state.update(inputs=snapshot.name, bundles=bundles)
        _write_json(self.directory / "install.json", self.state)

    def _rebuild(self, timeout: str) -> None:
        """Let platform installation own environment images and retain installed values."""

        settings = dict(self.state["command"])
        settings.update(values=(), timeout=timeout)
        command = InstallCommand(**settings)
        PlatformLifecycle(command.oci_registry).install(
            command,
            source_base_image=self.state.get("base_image"),
            source_build_arguments=self.state.get("build", {}).get("arguments"),
        )
        self.state = json.loads((self.directory / "install.json").read_text())
        self.selected.clear()

    def apply(
        self, deployment: ForetokenDeployment, timeout: str
    ) -> ForetokenDeployment:
        """Publish source bundles and return remaining intent for the final deployment apply."""
        if bundle := self.state["bundles"].get("control-plane"):
            self._publish_control_plane(bundle["revision"], timeout)
        objects = copy.deepcopy(deployment.objects)
        pending: dict[str, dict[str, dict[str, str]]] = {}
        for obj in objects:
            component = _COMPONENTS.get(obj.get("kind"))
            if component is None:
                continue
            metadata = obj["metadata"]
            annotations = metadata.setdefault("annotations", {})
            annotations.pop(SOURCE_REVISION, None)
            bundle = self.state["bundles"].get(component)
            namespace = metadata.get("namespace") or deployment.namespace or "default"
            if bundle is None:
                continue
            if component == "model-server" and obj["spec"].get("backend") != "vllm":
                raise DeploymentError(
                    "source runtime artifacts currently require the vLLM backend"
                )
            current = self.kubectl.get_if_exists(
                obj["kind"], metadata["name"], namespace
            )
            active = (
                (current or {})
                .get("metadata", {})
                .get("annotations", {})
                .get(SOURCE_REVISION)
            )
            if active != bundle["revision"]:
                self.selected[(obj["kind"], namespace, metadata["name"])] = bundle[
                    "revision"
                ]
                pending.setdefault(namespace, {})[component] = bundle
            annotations[SOURCE_REVISION] = bundle["revision"]
        if pending:
            # Storage can be prepared without requiring the previous engine to start.

            storage_kinds = {"Namespace", "RuntimeCache"}
            storage = tuple(
                o for o in deployment.objects if o.get("kind") in storage_kinds
            )
            if storage:
                DirectoryVolumes(self.kubectl).apply(
                    replace(
                        deployment,
                        objects=storage,
                        rendered=yaml.safe_dump_all(storage, sort_keys=False),
                    ),
                    timeout,
                )
            for namespace, bundles in pending.items():
                if not self._publish(namespace, bundles, timeout):
                    print(
                        f"{namespace} source storage is not ready or unavailable; updating images instead",
                        flush=True,
                    )
                    self._rebuild(timeout)
                    return self.apply(deployment, timeout)
            # Storage intent and directory bindings were applied before publication.
            # Return only the remaining resources so the final apply does not repeat them.
            objects = [o for o in objects if o.get("kind") not in storage_kinds]
        return parse_deployment(
            deployment.path, yaml.safe_dump_all(objects, sort_keys=False)
        )

    def _publish_control_plane(self, revision: str, timeout: str) -> None:
        """Build and activate platform executables without replacing their environment image."""

        platforms = self.kubectl.list_all_resources(
            ("deployments",),
            label_selector="app.kubernetes.io/name=foretoken-control-plane",
        )
        platform = next(
            item
            for item in platforms
            if item["metadata"]["uid"] == self.state["platform_uid"]
        )
        namespace = platform["metadata"]["namespace"]
        origin = ApplicationFiles(self.kubectl, namespace)
        reference = origin.reference("control-plane", revision)
        active = (
            platform["spec"]["template"]["metadata"]
            .get("annotations", {})
            .get("inference.foretoken.io/application-url", "")
        )
        resource = ResourceRef("Deployment", platform["metadata"]["name"], namespace)
        if active == reference:
            self.kubectl.rollout_status(resource, timeout)
            return
        origin.prepare(timeout)
        build = self.state["build"]
        mount = "/var/cache/foretoken"
        claim = find_build_cache(
            self.kubectl, namespace, build["binding"], origin.node, mount
        )
        if claim is None:
            node_uid = self.kubectl.get("node", origin.node)["metadata"]["uid"][:8]
            local_caches = local_build_nodes(
                self.kubectl, build["registry"], build["containerd_socket"]
            )
            claim = next(
                (claim for node, _, claim in local_caches if node == origin.node),
                "foretoken-application-build-" + node_uid,
            )
        ensure_build_cache(
            self.kubectl,
            namespace,
            claim,
            build["configuration"],
            owner={
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "name": origin.claim,
                "uid": origin.claim_uid,
            },
        )
        snapshot = self.directory / self.state["inputs"]
        inputs = {
            str(path.relative_to(snapshot)): path
            for path in snapshot.rglob("*")
            if path.is_file()
        }
        helm = Helm(default_platform_config(self.state["command"]["oci_registry"]))
        print("Preparing control-plane application files", flush=True)
        with ClusterBuilder(
            self.kubectl,
            namespace,
            claim,
            mount,
            build["configuration"]["image"],
            build["binding"],
            timeout,
            tools_image=image_tools_image(build["arguments"]),
            node=origin.node,
            credentials=registry_credentials(
                [
                    build["configuration"]["image"],
                    "docker.io",
                    "gcr.io",
                    *(
                        value
                        for key, value in build["arguments"].items()
                        if key.endswith("REGISTRY")
                    ),
                ]
            ),
            pull_secrets=origin.pull_secrets,
        ) as builder:
            builder.sync(inputs, build["versions"])
            output = builder.root + "/output/control-plane"
            builder.build(
                "control-plane/Dockerfile",
                target="source-export",
                destination=output,
                arguments=build["arguments"],
            )
            validate_build_inputs(self.root, snapshot, self.state.get("engines", {}))
            previous = (
                active.rsplit("/", 1)[-1]
                if active.startswith(origin.endpoint + "/control-plane/")
                else ""
            )
            # Publication retains Helm rollback history and delayed worker/Pod consumers.
            # Its Job releases the RWO origin before the controller starts its rollout.
            references = helm.control_plane_application_history()
            if references is not None:
                for task in self.kubectl.list_all_resources(("videotasks",)):
                    selected = (
                        task.get("status", {})
                        .get("plan", {})
                        .get("workerApplicationURL")
                    )
                    if selected:
                        references.add(selected)
                consumers = self.kubectl.list_all_resources(
                    ("pods", "replicasets"),
                    label_selector="foretoken.io/application-files=consumer",
                )
                for consumer in consumers:
                    metadata = (
                        consumer["metadata"]
                        if consumer["kind"] == "Pod"
                        else consumer["spec"]["template"]["metadata"]
                    )
                    if selected := metadata.get("annotations", {}).get(
                        "inference.foretoken.io/application-url"
                    ):
                        references.add(selected)
            origin.publish(
                builder, output, "control-plane", revision, previous, references
            )
            builder.run(["rm", "-rf", "--", output])
        helm.update_control_plane_application(snapshot, reference, timeout)
        self.kubectl.rollout_status(resource, timeout)

    def _publish(
        self, namespace: str, bundles: dict[str, dict[str, Any]], timeout: str
    ) -> bool:
        """Compile on separate storage and publish to the workload cache before rollout."""

        runtime = self.state["runtime"]
        build = self.state["build"]
        claim = runtime["claim"]
        directory_owner = None
        if not claim:
            caches = self.kubectl.list_resources(("runtimecache",), namespace)
            if not caches:
                return False
            if len(caches) != 1:
                raise DeploymentError(
                    f"namespace {namespace} has multiple RuntimeCaches"
                )
            name = caches[0]["metadata"]["name"]
            self.kubectl.run(
                [
                    "wait",
                    f"runtimecache/{name}",
                    "-n",
                    namespace,
                    "--for=jsonpath={.status.claimName}",
                    f"--timeout={timeout}",
                ]
            )
            cache = self.kubectl.get("runtimecache", name, namespace)
            claim = cache["status"]["claimName"]
            directory_owner = DirectoryVolumes.read_directory_owner(cache)
        pvc = self.kubectl.get("pvc", claim, namespace)
        # Keep first GPU-node placement with the model preparation controller.
        if (
            pvc.get("status", {}).get("phase") != "Bound"
            and "ReadWriteMany" not in pvc["spec"]["accessModes"]
        ):
            return False
        mounts = [
            pod
            for pod in self.kubectl.list_resources(("pods",), namespace)
            if pod["spec"].get("nodeName")
            and any(
                volume.get("persistentVolumeClaim", {}).get("claimName") == claim
                for volume in pod["spec"].get("volumes", [])
            )
        ]
        mounts.sort(
            key=lambda pod: (
                pod.get("status", {}).get("phase") != "Running",
                bool(pod["metadata"].get("deletionTimestamp")),
            )
        )
        node = mounts[0]["spec"]["nodeName"] if mounts else ""
        local_nodes = local_build_nodes(
            self.kubectl, build["registry"], build["containerd_socket"]
        )
        socket = local_nodes[0][1]
        if socket and not node:
            node = local_nodes[0][0]
        node_uid = (
            self.kubectl.get("node", node)["metadata"]["uid"][:8] if node else "shared"
        )
        build_claim = f"foretoken-source-build-{pvc['metadata']['uid'][:8]}-{node_uid}"
        ensure_build_cache(
            self.kubectl,
            namespace,
            build_claim,
            build["configuration"],
            owner={
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "name": claim,
                "uid": pvc["metadata"]["uid"],
            },
        )
        snapshot = self.directory / self.state["inputs"]
        files = {
            str(path.relative_to(snapshot)): path
            for path in snapshot.rglob("*")
            if path.is_file()
        }
        with ClusterBuilder(
            self.kubectl,
            namespace,
            build_claim,
            "/var/cache/foretoken-build",
            build["configuration"]["image"],
            build["binding"],
            timeout,
            tools_image=image_tools_image(build["arguments"]),
            node=node,
            containerd_socket=socket,
            pull_secrets=tuple(runtime["pull_secrets"]),
            publisher_image=runtime["model_image"],
            runtime_claim=claim,
            runtime_mount=runtime["mount"],
            runtime_owner=directory_owner,
            credentials=registry_credentials(
                [
                    runtime["model_image"],
                    build["configuration"]["image"],
                    "docker.io",
                    "ghcr.io",
                    *(
                        value
                        for key, value in build["arguments"].items()
                        if key.endswith("REGISTRY")
                    ),
                ]
            ),
        ) as builder:
            builder.sync(files, build["versions"])
            for component, bundle in bundles.items():
                revision = bundle["revision"]
                destination = runtime["mount"] + "/source/" + revision
                if builder.read_json(
                    destination + "/complete.json", container="publisher"
                ):
                    continue
                staging = builder.root + "/output/" + revision
                payload = staging + "/payload"
                builder.run(["rm", "-rf", "--", staging])
                builder.run(["mkdir", "-p", payload])
                if bundle["compile"]:
                    builder.build(
                        f"data-plane/{component}/Dockerfile",
                        target="source-export",
                        destination=staging + "/runtime",
                        arguments=build["arguments"],
                    )
                    builder.run(
                        [
                            "sh",
                            "-ec",
                            'cp -R "$1/." "$2/"',
                            "assemble",
                            staging + "/runtime",
                            payload,
                        ]
                    )
                if component == "model-server":
                    builder.run(
                        [
                            "cp",
                            "-R",
                            builder.workspace + "/data-plane/model-server/python",
                            payload + "/python",
                        ]
                    )
                    if self.state.get("engines"):
                        builder.build(
                            "deploy/inference-engines/source-build.Dockerfile",
                            target="source-export",
                            destination=staging + "/engine",
                            arguments={
                                **build["arguments"],
                                "RUNTIME_IMAGE": runtime["model_image"],
                                "CACHE_ID": build["binding"]
                                + "-"
                                + build["environment"],
                                "BUILD_NATIVE": str(
                                    build.get("engine_native", False)
                                ).lower(),
                            },
                        )
                        builder.run(
                            [
                                "sh",
                                "-ec",
                                'cp -R "$1/." "$2/"',
                                "assemble",
                                staging + "/engine",
                                payload,
                            ]
                        )
                builder.publish(
                    payload,
                    destination,
                    {
                        "revision": revision,
                        "binding": build["binding"],
                        "component": component,
                        "executable": f"foretoken-{component}"
                        if bundle["compile"]
                        else None,
                    },
                )
                builder.run(["rm", "-rf", "--", staging])
            self._retire_sources(builder)
        return True

    def _retire_sources(self, builder: ClusterBuilder) -> None:
        """Retire this binding's unreferenced payloads while preserving shared-volume consumers."""
        # Namespaces may mount the same data directory. Include retained rollout
        # templates and terminating/preparation Pods, not just currently Ready services.
        objects = list(
            self.kubectl.list_all_resources(
                ("modelservice", "frontendservice", "modelpool", "modelgroup")
            )
        )
        for label in (
            "inference.foretoken.io/model-group",
            "inference.foretoken.io/frontend-service",
            "inference.foretoken.io/model-preparation-group",
        ):
            objects.extend(
                self.kubectl.list_all_resources(
                    ("pods", "jobs", "replicasets", "deployments"), label_selector=label
                )
            )
        keep = {bundle["revision"] for bundle in self.state["bundles"].values()}
        for obj in objects:
            spec = obj.get("spec", {})
            template = spec.get("template", {})
            keep.update(
                filter(
                    None,
                    (
                        obj["metadata"].get("annotations", {}).get(SOURCE_REVISION),
                        template.get("metadata", {})
                        .get("annotations", {})
                        .get(SOURCE_REVISION),
                        template.get("sourceRevision"),
                        spec.get("runtime", {}).get("sourceRevision"),
                    ),
                )
            )
            pod_spec = spec if obj["kind"] == "Pod" else template.get("spec", {})
            for container in (
                *pod_spec.get("containers", []),
                *pod_spec.get("initContainers", []),
            ):
                for variable in container.get("env", []):
                    if variable[
                        "name"
                    ] == "FORETOKEN_SOURCE_DIRECTORY" and variable.get("value"):
                        keep.add(variable["value"].rstrip("/").rsplit("/", 1)[-1])
        script = """import json, shutil, sys
from pathlib import Path
selection = json.load(sys.stdin)
root = Path(sys.argv[1])
for directory in root.iterdir():
    if not directory.is_dir() or directory.name in selection["keep"]:
        continue
    manifest = directory / "complete.json"
    if not manifest.is_file():
        continue
    try:
        bundle = json.loads(manifest.read_text())
        if isinstance(bundle, dict) and bundle.get("binding") == selection["binding"] and bundle.get("revision") == directory.name:
            shutil.rmtree(directory)
    except (OSError, ValueError) as error:
        print(f"Source cache cleanup: {directory.name}: {error}", file=sys.stderr)
"""
        builder.run(
            [
                "sh",
                "-ec",
                'exec "${FORETOKEN_VLLM_PYTHON:-python}" -c "$1" "$2"',
                "retire",
                script,
                self.state["runtime"]["mount"] + "/source",
            ],
            container="publisher",
            input_text=json.dumps(
                {"binding": self.state["build"]["binding"], "keep": sorted(keep)}
            ),
        )

    def _ready_containers(
        self, namespace: str, component: str, service: str, revision: str
    ) -> list[tuple[str, str, str, str]]:
        """Select ready containers and route identities from the committed source or image cohort."""
        containers = []
        selected = {}
        seen_pools = set()
        if component == "model-server":
            current = self.kubectl.get("modelservice", service, namespace)
            selected = {
                p["poolUID"]: p["revision"]
                for p in current.get("status", {}).get("servingPoolRevisions", [])
            }
        for pod in self.kubectl.list_resources(("pods",), namespace):
            metadata = pod["metadata"]
            if (
                metadata.get("deletionTimestamp")
                or metadata.get("annotations", {}).get(SOURCE_REVISION, "") != revision
            ):
                continue
            if not any(
                c["type"] == "Ready" and c["status"] == "True"
                for c in pod.get("status", {}).get("conditions", [])
            ):
                continue
            labels = metadata.get("labels", {})
            expected_image = self.state["runtime"]["image"]
            route_target = ""
            if component == "frontend":
                if labels.get("inference.foretoken.io/frontend-service") != service:
                    continue
            else:
                group_name = labels.get("inference.foretoken.io/model-group")
                if not group_name:
                    continue
                group = self.kubectl.get_if_exists("modelgroup", group_name, namespace)
                if group is None:
                    continue
                pool = self.kubectl.get_if_exists(
                    "modelpool", group["spec"]["modelPoolRef"]["name"], namespace
                )
                if (
                    pool is None
                    or group["spec"]["modelPoolRef"]["uid"] != pool["metadata"]["uid"]
                ):
                    continue
                runtime = group["spec"]["runtime"]
                if (
                    pool["spec"]["modelServiceRef"]["name"] != service
                    or selected.get(pool["metadata"]["uid"])
                    != group["spec"]["revision"]
                    or runtime.get("sourceRevision", "") != revision
                ):
                    continue
                image_key = (
                    "omni_image"
                    if runtime["backend"] == "vllm-omni"
                    else "nsight_image"
                    if runtime.get("profiling", {}).get("engine") == "nsight"
                    else "model_image"
                )
                expected_image = self.state["runtime"][image_key]
                if runtime["image"] != expected_image:
                    continue
                seen_pools.add(pool["metadata"]["uid"])
                route_target = group["metadata"]["uid"]
            for container in pod["spec"]["containers"]:
                if (
                    container["name"] == component
                    and container["image"] == expected_image
                ):
                    directory = next(
                        (
                            e.get("value", "")
                            for e in container.get("env", [])
                            if e["name"] == "FORETOKEN_SOURCE_DIRECTORY"
                        ),
                        "",
                    )
                    containers.append(
                        (metadata["name"], component, directory, route_target)
                    )
        if component == "model-server" and seen_pools != set(selected):
            return []
        return containers

    def _frontend_routes_ready(
        self,
        namespace: str,
        service: str,
        writers: list[tuple[str, str, str, str]],
        route_targets: set[str],
        deadline: float,
    ) -> bool:
        """Observe the existing routing publication, consumer acknowledgements and Service endpoints."""
        deployment = self.kubectl.get("deployment", service, namespace)
        config_name = next(
            volume["configMap"]["name"]
            for volume in deployment["spec"]["template"]["spec"]["volumes"]
            if volume["name"] == "serving"
        )
        config_map = self.kubectl.get_if_exists("configmap", config_name, namespace)
        if config_map is None:
            return False
        snapshot = json.loads(config_map["data"]["serving.json"])
        published = {
            route["route_target_id"]
            for section in ("groups", "pd_components", "epd_components")
            for route in (snapshot.get(section) or [])
        }
        if not route_targets <= published:
            return False
        pods = [
            pod
            for pod in self.kubectl.list_resources(("pods",), namespace)
            if not pod["metadata"].get("deletionTimestamp")
            and pod["metadata"]
            .get("labels", {})
            .get("inference.foretoken.io/frontend-service")
            == service
        ]
        if len(pods) < deployment["spec"]["replicas"] or {
            pod["metadata"]["name"] for pod in pods
        } != {name for name, _, _, _ in writers}:
            return False
        for pod in pods:
            container = next(
                c for c in pod["spec"]["containers"] if c["name"] == "frontend"
            )
            port = next(
                port["containerPort"]
                for port in container["ports"]
                if port["name"] == "http"
            )
            state = json.loads(
                self.kubectl.get_raw(
                    f"/api/v1/namespaces/{namespace}/pods/http:{pod['metadata']['name']}:{port}/proxy/statusz",
                    f"{max(1, int(deadline - time.monotonic()))}s",
                )
            )
            if (
                not state["serving_ready"]
                or state["active_generation"] != snapshot["version"]
            ):
                return False
        endpoints = {
            endpoint.get("targetRef", {}).get("uid")
            for value in self.kubectl.list_resources(("endpointslices",), namespace)
            if value["metadata"].get("labels", {}).get("kubernetes.io/service-name")
            == service
            for endpoint in value.get("endpoints", [])
            if endpoint.get("conditions", {}).get("ready") is True
        }
        return bool(pods) and {pod["metadata"]["uid"] for pod in pods} <= endpoints

    def verify(
        self,
        deployment: ForetokenDeployment,
        timeout: str,
        *,
        observe: Callable[[], None] | None = None,
    ) -> None:
        """Wait for changed runtime code and its frontend routing consumers to become active."""
        deadline = time.monotonic() + timeout_seconds(timeout)
        routes: dict[str, set[str]] = {}
        consumers = dict(self.selected)
        # Unchanged frontend code still needs to consume a new backend cohort.
        if any(kind == "ModelService" for kind, _, _ in self.selected):
            for obj in deployment.objects:
                if obj.get("kind") == "FrontendService":
                    metadata = obj["metadata"]
                    key = (
                        "FrontendService",
                        deployment.namespace or "default",
                        metadata["name"],
                    )
                    consumers.setdefault(
                        key, metadata.get("annotations", {}).get(SOURCE_REVISION, "")
                    )
        # Source annotations do not advance Service generation. Verify committed
        # backend code first, then the routing consumers of that exact cohort.
        selected = sorted(
            consumers.items(), key=lambda item: item[0][0] == "FrontendService"
        )
        for (kind, namespace, service), revision in selected:
            component = _COMPONENTS[kind]
            code_changed = (kind, namespace, service) in self.selected
            if component == "frontend" and code_changed:
                self.kubectl.rollout_status(
                    ResourceRef("Deployment", service, namespace),
                    f"{max(1, int(deadline - time.monotonic()))}s",
                )
            while True:
                if observe is not None:
                    observe()
                writers = self._ready_containers(
                    namespace, component, service, revision
                )
                if writers and (
                    component != "frontend"
                    or self._frontend_routes_ready(
                        namespace,
                        service,
                        writers,
                        routes.get(namespace, set()),
                        deadline,
                    )
                ):
                    break
                if time.monotonic() >= deadline:
                    raise DeploymentError(
                        f"timed out waiting for {namespace}/{service} to activate source {revision}"
                    )
                time.sleep(2)
            if component == "model-server":
                routes.setdefault(namespace, set()).update(
                    route for _, _, _, route in writers
                )
            if not code_changed:
                continue
            for pod, container, directory, _ in writers:
                expected = (
                    f"FORETOKEN_ACTIVE_SOURCE_DIRECTORY={directory}" if revision else ""
                )
                output = self.kubectl.run(
                    [
                        "exec",
                        "-n",
                        namespace,
                        pod,
                        "-c",
                        container,
                        "--",
                        "sh",
                        "-c",
                        'grep -z "^FORETOKEN_ACTIVE_SOURCE_DIRECTORY=" /proc/1/environ; status=$?; test "$status" -le 1',
                    ]
                ).stdout.strip("\x00\n")
                if output != expected:
                    raise DeploymentError(
                        f"{namespace}/{pod} did not activate source {revision}"
                    )
