# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project


"""Load HuggingFace dataset rows for benchmark workloads."""

from __future__ import annotations

from typing import Any, Iterator

from datasets import get_dataset_config_names, get_dataset_split_names, load_dataset

_DEFAULT_SELECTORS = {
    "KrisQ/StudyChat": "train",
    "valeriol29/mooncake-traces": "conversation",
}


def parse_hf_dataset_spec(spec: str) -> tuple[str, str]:
    """Parse a supported dataset selector into ``(dataset_id, selector)``.

    A selector may be a split or a builder config. Known trace datasets have
    defaults; other datasets must use ``org/name:split``.
    """
    if ":" not in spec:
        selector = _DEFAULT_SELECTORS.get(spec)
        if selector is not None:
            return spec, selector
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


def is_hf_dataset_spec(spec: str) -> bool:
    """Return whether ``spec`` is a supported Hugging Face selector."""
    try:
        parse_hf_dataset_spec(spec)
    except ValueError:
        return False
    return True


def same_dataset_source(left: str, right: str) -> bool:
    """Return whether two selectors resolve to the same dataset source."""
    if left == right:
        return True
    try:
        return parse_hf_dataset_spec(left) == parse_hf_dataset_spec(right)
    except ValueError:
        return False


def _load_hf_data(dataset_id: str, split: str) -> Any:
    """Load a cached HF dataset for ``dataset_id`` / ``split``.

    Some hubs publish named builder configs whose only data split is
    ``train``; the CLI ``split`` then selects that config name.
    """
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
        )
    return load_dataset(dataset_id, split=split)


def iter_hf_rows(spec: str) -> Iterator[tuple[int, Any]]:
    """Yield ``(row_index, row_dict)`` from a HuggingFace dataset spec."""
    dataset_id, split = parse_hf_dataset_spec(spec)
    data = _load_hf_data(dataset_id, split)
    for row_index, row in enumerate(data):
        yield row_index, dict(row)
