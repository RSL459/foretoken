# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Observe controller-reported ModelService replica capacity during one benchmark run."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from benchmarks.results.timeseries import ELAPSED_TIME
from foretoken.kubernetes import Kubectl
from foretoken.manifest import DeploymentError, ResourceRef

logger = logging.getLogger(__name__)

DEFAULT_REPLICA_SAMPLE_INTERVAL_SECONDS = 1.0
DEFAULT_REPLICA_KUBECTL_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class ReplicaTargetObservation:
    """Record applied desired and Ready replicas for one controller scaling target."""

    target_id: str
    role: str
    desired_replicas: int
    ready_replicas: int


@dataclass(frozen=True)
class ReplicaObservation:
    """Record all replica targets returned by one ModelService status read."""

    observed_at: float
    model: str
    model_service: str
    targets: tuple[ReplicaTargetObservation, ...]


class KubernetesReplicaObserver:
    """Own bounded kubectl sampling for one benchmark workload point.

    The observer uses ``time.perf_counter`` like the request clients. ``finish``
    aligns samples to the caller-provided request time origin and returns rows
    suitable for both the local raw artifact and W&B history.
    """

    def __init__(self, resources: tuple[ResourceRef, ...], model: str) -> None:
        self._resources = resources
        self._model = model
        self._kubectl = Kubectl()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._observations: list[ReplicaObservation] = []
        self._errors = 0
        self._last_error: str | None = None

    def start(self) -> None:
        """Start immediate sampling in one owned background thread."""
        if self._thread is not None:
            raise RuntimeError("replica observer is already active")
        self._thread = threading.Thread(
            target=self._run,
            name="foretoken-benchmark-replicas",
        )
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                observations = self._read_observations()
            except (DeploymentError, KeyError, TypeError, ValueError) as exc:
                self._errors += 1
                self._last_error = str(exc)
            else:
                self._observations.extend(observations)
            self._stop.wait(DEFAULT_REPLICA_SAMPLE_INTERVAL_SECONDS)

    def _read_observations(self) -> tuple[ReplicaObservation, ...]:
        observed_at = time.perf_counter()
        values = self._kubectl.get_resources(
            self._resources,
            timeout=DEFAULT_REPLICA_KUBECTL_TIMEOUT_SECONDS,
        )
        by_name = {
            str((value.get("metadata") or {}).get("name") or ""): value
            for value in values
        }
        observations: list[ReplicaObservation] = []
        for resource in self._resources:
            value = by_name.get(resource.name)
            if value is None:
                raise DeploymentError(
                    f"kubectl omitted ModelService/{resource.name}"
                )
            metadata = value.get("metadata") or {}
            status = value.get("status") or {}
            if not isinstance(metadata, dict) or not isinstance(status, dict):
                raise TypeError("ModelService returned invalid metadata or status")
            if status.get("observedGeneration") != metadata.get("generation"):
                continue
            raw_targets = status.get("autoscaling")
            if not isinstance(raw_targets, list) or not raw_targets:
                continue

            targets: list[ReplicaTargetObservation] = []
            for item in raw_targets:
                if not isinstance(item, dict):
                    raise TypeError(
                        "ModelService autoscaling status contains a non-object target"
                    )
                target_id = item.get("id")
                role = item.get("role")
                desired = item.get("appliedReplicas")
                ready = item.get("readyReplicas")
                if not isinstance(target_id, str) or not target_id:
                    raise ValueError("ModelService autoscaling target has no id")
                if not isinstance(role, str) or not role:
                    raise ValueError(
                        f"ModelService autoscaling target {target_id!r} has no role"
                    )
                if (
                    not isinstance(desired, int)
                    or isinstance(desired, bool)
                    or not isinstance(ready, int)
                    or isinstance(ready, bool)
                ):
                    raise TypeError(
                        f"ModelService autoscaling target {target_id!r} has invalid replica counts"
                    )
                targets.append(
                    ReplicaTargetObservation(
                        target_id=target_id,
                        role=role,
                        desired_replicas=desired,
                        ready_replicas=ready,
                    )
                )
            targets.sort(key=lambda item: item.target_id)
            observations.append(
                ReplicaObservation(
                    observed_at=observed_at,
                    model=self._model,
                    model_service=resource.name,
                    targets=tuple(targets),
                )
            )
        return tuple(observations)

    def finish(self, time_origin: float) -> list[dict[str, Any]]:
        """Stop sampling and return observations aligned to the request time axis."""
        self.close()
        if self._errors:
            logger.warning(
                "Replica observation skipped %d Kubernetes reads; last error: %s",
                self._errors,
                self._last_error,
            )
        if not self._observations:
            logger.warning(
                "No current replica status was available for %s",
                ", ".join(
                    f"ModelService/{resource.name}" for resource in self._resources
                ),
            )
            return []

        before: dict[str, ReplicaObservation] = {}
        selected: list[ReplicaObservation] = []
        for item in self._observations:
            if item.observed_at <= time_origin:
                before[item.model_service] = item
            else:
                selected.append(item)
        selected.extend(before.values())
        selected.sort(key=lambda item: (item.observed_at, item.model_service))
        rows: list[dict[str, Any]] = []
        for item in selected:
            rows.append(
                {
                    "elapsed_time_s": max(0.0, item.observed_at - time_origin),
                    "model": item.model,
                    "model_service": item.model_service,
                    "targets": [
                        {
                            "id": target.target_id,
                            "role": target.role,
                            "desired_replicas": target.desired_replicas,
                            "ready_replicas": target.ready_replicas,
                        }
                        for target in item.targets
                    ],
                }
            )
        return rows

    def close(self) -> None:
        """Stop and join the owned sampling thread; repeated calls are harmless."""
        thread = self._thread
        if thread is None:
            return
        self._thread = None
        self._stop.set()
        thread.join()


def replica_history_rows(
    observations: list[dict[str, Any]],
) -> list[dict[str, float]]:
    """Map raw replica observations to W&B scalar histories on the shared time axis."""
    rows: list[dict[str, float]] = []
    for observation in observations:
        row: dict[str, float] = {
            ELAPSED_TIME: float(observation["elapsed_time_s"]),
        }
        model_service = str(observation["model_service"])
        for target in observation["targets"]:
            prefix = f"Replicas/{model_service}/{target['id']}"
            row[f"{prefix}/Desired replicas"] = float(target["desired_replicas"])
            row[f"{prefix}/Ready replicas"] = float(target["ready_replicas"])
        rows.append(row)
    return rows
