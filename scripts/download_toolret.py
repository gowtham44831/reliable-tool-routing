#!/usr/bin/env python
"""Download a subset of the ToolRet benchmark from the Hugging Face Hub.

This script only downloads small query subsets (hundreds of rows each) and
the three ToolRet-Tools corpora (code/customized/web, ~44.5k tool docs,
~9 MB total). It requires network access and the optional ``data`` extra
(``pip install -e ".[data]"``).

Nothing here is executed or called -- these are static text records of
tool descriptions, never invoked.

Usage:
    python scripts/download_toolret.py --queries apibank apigen \
        --out-dir data/raw/toolret

Downloaded files are written under ``--out-dir`` as parquet, together with
a ``manifest.json`` recording the resolved dataset git revision, per-file
sha256 checksums, and download timestamp, for reproducibility (see
docs/dataset.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from datasets import load_dataset
    from huggingface_hub import HfApi
except ImportError:  # pragma: no cover
    print(
        "Missing optional dependencies. Install with: pip install -e '.[data]'",
        file=sys.stderr,
    )
    raise

from tool_routing.data.toolret_constants import (
    QUERIES_REPO,
    SINGLE_TOOL_SUBSETS,
    TOOLS_REPO,
    TOOLS_SUBSETS,
)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queries",
        nargs="+",
        default=list(SINGLE_TOOL_SUBSETS),
        help="ToolRet-Queries subset names to download (default: all "
        "subsets classified as single-tool in toolret_constants.py).",
    )
    parser.add_argument(
        "--out-dir", default="data/raw/toolret", help="Output directory."
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    (out_dir / "queries").mkdir(parents=True, exist_ok=True)
    (out_dir / "tools").mkdir(parents=True, exist_ok=True)

    api = HfApi()
    manifest = {
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
        "queries_repo": QUERIES_REPO,
        "tools_repo": TOOLS_REPO,
        "queries_subsets": args.queries,
        "tools_subsets": list(TOOLS_SUBSETS),
        "files": {},
    }
    for repo_id, key in [(QUERIES_REPO, "queries_revision"), (TOOLS_REPO, "tools_revision")]:
        info = api.dataset_info(repo_id)
        manifest[key] = info.sha

    for subset in args.queries:
        print(f"Downloading queries subset: {subset}")
        ds = load_dataset(QUERIES_REPO, name=subset, split="queries")
        out_path = out_dir / "queries" / f"{subset}.parquet"
        ds.to_parquet(str(out_path))
        manifest["files"][f"queries/{subset}.parquet"] = {
            "rows": ds.num_rows,
            "sha256": sha256_of(out_path),
        }

    for subset in TOOLS_SUBSETS:
        print(f"Downloading tools subset: {subset}")
        ds = load_dataset(TOOLS_REPO, name=subset, split="tools")
        out_path = out_dir / "tools" / f"{subset}.parquet"
        ds.to_parquet(str(out_path))
        manifest["files"][f"tools/{subset}.parquet"] = {
            "rows": ds.num_rows,
            "sha256": sha256_of(out_path),
        }

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"Wrote manifest to {manifest_path}")


if __name__ == "__main__":
    main()
