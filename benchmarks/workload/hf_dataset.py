# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project


"""Hugging Face dataset id and file-URI loaders."""

from __future__ import annotations

from typing import Any, Iterator, Optional

from datasets import get_dataset_config_names, get_dataset_split_names, load_dataset
from huggingface_hub import hf_hub_download

_HF_DATASETS_PREFIX = "hf://datasets/"


def is_hf_file_uri(source: str) -> bool:
    """Return True for canonical ``hf://datasets/...`` file URIs."""
    return source.startswith(_HF_DATASETS_PREFIX)


def parse_hf_file_uri(uri: str) -> tuple[str, Optional[str], str]:
    """Parse ``hf://datasets/{repo_id}[@{revision}]/{path}``.

    Returns ``(repo_id, revision_or_none, filename)``.
    """
    if not uri.startswith(_HF_DATASETS_PREFIX):
        if uri.startswith("hf://"):
            raise ValueError(
                f"Invalid HF file URI {uri!r}. "
                "Use hf://datasets/{{repo_id}}[@{{revision}}]/path} "
                "(repo type 'datasets' is required)."
            )
        raise ValueError(
            f"Invalid HF file URI {uri!r}. "
            "Use hf://datasets/{{repo_id}}[@{{revision}}]/path}."
        )

    remainder = uri[len(_HF_DATASETS_PREFIX) :]
    if not remainder or remainder.startswith("/"):
        raise ValueError(
            f"Invalid HF file URI {uri!r}. "
            "Use hf://datasets/{{repo_id}}[@{{revision}}]/path}."
        )

    if "@" in remainder:
        repo_id, after_at = remainder.split("@", 1)
        if not repo_id or "/" not in after_at:
            raise ValueError(
                f"Invalid HF file URI {uri!r}. "
                "Use hf://datasets/{{repo_id}}@{{revision}}/{{path}}."
            )
        revision, filename = after_at.split("/", 1)
        if not revision or not filename:
            raise ValueError(
                f"Invalid HF file URI {uri!r}. "
                "Use hf://datasets/{{repo_id}}@{{revision}}/{{path}}."
            )
        return repo_id, revision, filename

    parts = remainder.split("/")
    if len(parts) >= 3 and all(parts):
        repo_id = f"{parts[0]}/{parts[1]}"
        filename = "/".join(parts[2:])
        return repo_id, None, filename
    if len(parts) == 2 and parts[0] and parts[1]:
        return parts[0], None, parts[1]
    raise ValueError(
        f"Invalid HF file URI {uri!r}. "
        "Use hf://datasets/{{repo_id}}[@{{revision}}]/path}."
    )


def resolve_hf_file_uri(uri: str) -> str:
    """Cache an HF dataset-repo file and return the local path."""
    repo_id, revision, filename = parse_hf_file_uri(uri)
    return hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        repo_type="dataset",
        revision=revision,
    )


def parse_hf_dataset_spec(spec: str) -> tuple[str, str]:
    """Parse ``org/name:split`` into ``(dataset_id, split)``."""
    if ":" not in spec:
        raise ValueError(
            f"Invalid HuggingFace dataset spec {spec!r}. "
            "Use 'org/name:split' (split is required)."
        )
    dataset_id, split = spec.rsplit(":", 1)
    if not dataset_id or not split:
        raise ValueError(
            f"Invalid HuggingFace dataset spec {spec!r}. "
            "Use 'org/name:split'."
        )
    return dataset_id, split


def _load_hf_data(dataset_id: str, split: str) -> Any:
    """Load a streaming HF dataset for ``dataset_id`` / ``split``."""
    configs = get_dataset_config_names(dataset_id)
    if split in configs:
        data_splits = get_dataset_split_names(dataset_id, split)
        if len(data_splits) != 1:
            raise ValueError(
                f"HuggingFace dataset {dataset_id!r} config {split!r} has "
                f"multiple data splits {data_splits}; expected exactly one."
            )
        return load_dataset(
            dataset_id,
            name=split,
            split=data_splits[0],
            streaming=True,
        )
    return load_dataset(dataset_id, split=split, streaming=True)


def iter_hf_rows(spec: str) -> Iterator[tuple[int, Any]]:
    """Yield ``(row_index, row_dict)`` from a HuggingFace dataset spec."""
    dataset_id, split = parse_hf_dataset_spec(spec)
    data = _load_hf_data(dataset_id, split)
    for row_index, row in enumerate(data):
        yield row_index, dict(row)
