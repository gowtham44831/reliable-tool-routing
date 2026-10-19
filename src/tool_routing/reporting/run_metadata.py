"""Capture reproducibility metadata for a run (section 9 of the spec)."""
from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

_TRACKED_PACKAGES = [
    "numpy",
    "pandas",
    "rank-bm25",
    "sentence-transformers",
    "scikit-learn",
    "matplotlib",
    "PyYAML",
    "pytest",
    "torch",
    "datasets",
    "huggingface-hub",
]


def _git_commit() -> str | None:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        )
        return out.stdout.strip()
    except Exception:
        return None


def _dependency_versions() -> dict[str, str]:
    versions = {}
    for pkg in _TRACKED_PACKAGES:
        try:
            versions[pkg] = version(pkg)
        except PackageNotFoundError:
            versions[pkg] = "not installed"
    return versions


def _device_info() -> dict:
    info = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": sys.version,
    }
    try:
        import torch

        info["torch_cuda_available"] = torch.cuda.is_available()
        info["torch_mps_available"] = (
            hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        )
    except Exception:
        info["torch_cuda_available"] = None
        info["torch_mps_available"] = None
    return info


def collect_run_metadata(config: dict, seed: int) -> dict:
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "dependency_versions": _dependency_versions(),
        "device_info": _device_info(),
        "seed": seed,
        "config": config,
    }


def write_run_metadata(path: str | Path, config: dict, seed: int) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(collect_run_metadata(config, seed), indent=2, sort_keys=True))
