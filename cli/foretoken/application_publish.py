# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright contributors to the Foretoken project

"""Publish completed build files on the platform's persistent application volume."""

from __future__ import annotations

import filecmp
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path


def publish(
    source: Path, destination: Path, binding: str, previous: Path | None
) -> None:
    """Expose an immutable directory, sharing unchanged files with its previous version."""
    if (destination / "manifest.json").is_file():
        return
    if not source.is_dir():
        raise FileNotFoundError(f"application export is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    prefix = f".{binding}.staging-"
    for abandoned in destination.parent.glob(prefix + "*"):
        shutil.rmtree(abandoned)
    with tempfile.TemporaryDirectory(
        prefix=prefix, dir=destination.parent
    ) as temporary:
        staging = Path(temporary) / "payload"
        staging.mkdir()
        files = []
        for origin in sorted(source.rglob("*")):
            if origin.is_symlink():
                raise ValueError(
                    f"application exports must not contain symlinks: {origin}"
                )
            if origin.is_dir():
                continue
            if not origin.is_file():
                raise ValueError(
                    f"application exports must contain regular files: {origin}"
                )
            relative = origin.relative_to(source)
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            mode = (stat.S_IMODE(origin.stat().st_mode) & 0o111) | 0o444
            old = previous / relative if previous is not None else None
            if (
                old is not None
                and old.is_file()
                and ((stat.S_IMODE(old.stat().st_mode) & 0o111) | 0o444) == mode
                and filecmp.cmp(origin, old, shallow=False)
            ):
                os.link(old, target)
            else:
                shutil.copyfile(origin, target)
                target.chmod(mode)
            files.append(
                {
                    "path": relative.as_posix(),
                    "mode": mode,
                    "size": target.stat().st_size,
                }
            )
        (staging / "manifest.json").write_text(
            json.dumps({"binding": binding, "files": files}) + "\n"
        )
        staging.rename(destination)


def retire(directory: Path, binding: str, keep: set[str]) -> None:
    """Remove this publisher's completed versions after their consumers and history retire."""
    for version in directory.iterdir():
        manifest = version / "manifest.json"
        if version.name in keep or not manifest.is_file():
            continue
        metadata = json.loads(manifest.read_text())
        if metadata.get("binding") == binding:
            shutil.rmtree(version)


if __name__ == "__main__":
    destination = Path(sys.argv[2])
    binding = sys.argv[3]
    publish(
        Path(sys.argv[1]),
        destination,
        binding,
        Path(sys.argv[4]) if sys.argv[4] else None,
    )
    retained = json.loads(sys.argv[5])
    if retained is not None:
        retire(destination.parent, binding, set(retained) | {destination.name})
