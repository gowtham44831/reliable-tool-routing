"""Write the frozen-evaluation manifest.

    python scripts/make_eval_manifest.py --out results/argverify_eval_v2_run1/MANIFEST.json

Records git commit + dirty flag, sha256 of every implementation file,
dataset / guide / policy / label file hashes, prompt sha, model ids (and
Ollama digest + quantization for local models), effective limits,
reasoning settings, timeout/retry policy, and hardware. Never records
credentials: the API key env var is reported only as present/absent.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path

IMPL = ["src/tool_routing/argverify/schema.py", "src/tool_routing/argverify/evidence.py",
        "src/tool_routing/argverify/methods.py", "src/tool_routing/argverify/policy.py",
        "src/tool_routing/argverify/llm.py", "src/tool_routing/argverify/llm_v2.py",
        "src/tool_routing/argverify/llm_providers.py", "src/tool_routing/argverify/evaluate.py",
        "scripts/run_argverify_eval.py"]
DATA = ["src/tool_routing/argverify/fixtures/labelset_v2.json",
        "src/tool_routing/argverify/fixtures/labelset_v2.CHANGELOG.md",
        "docs/argument_verification_annotation_guide.md"]


def sha(p: str) -> str | None:
    f = Path(p)
    return hashlib.sha256(f.read_bytes()).hexdigest() if f.exists() else None


def git(*args) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unavailable"


def ollama_info(model: str) -> dict:
    try:
        out = subprocess.check_output(["ollama", "show", model], text=True, timeout=20)
        info = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] in ("quantization", "parameters", "architecture"):
                info[parts[0]] = parts[1]
            if "context" in line and "length" in line:
                info["context_length"] = parts[-1]
        ls = subprocess.check_output(["ollama", "list"], text=True, timeout=20)
        for line in ls.splitlines():
            if line.startswith(model):
                info["digest"] = line.split()[1]
        return info
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--labels", nargs="*", default=[],
                    help="label CSVs merged for this evaluation")
    ap.add_argument("--dev-cases", nargs="*", default=[],
                    help="case ids used to revise methods (reclassified as development)")
    args = ap.parse_args()

    from tool_routing.argverify.llm_providers import PROMPT_SHA

    model = os.environ.get("ARGVERIFY_MODEL", "")
    provider = os.environ.get("ARGVERIFY_PROVIDER", "openai_compat")
    m = {
        "git": {"commit": git("rev-parse", "HEAD"),
                "dirty": bool(git("status", "--porcelain")),
                "branch": git("rev-parse", "--abbrev-ref", "HEAD")},
        "implementation_sha256": {p: sha(p) for p in IMPL},
        "dataset": {p: sha(p) for p in DATA},
        "annotation_guide_version": "2.1",
        "policy_version": "AcmeAir P1-P3 as stated in labelset_v2 shared_tool_schema",
        "labels": {p: sha(p) for p in args.labels},
        "development_cases_excluded_from_test_claims": args.dev_cases,
        "prompt_sha": PROMPT_SHA,
        "model": {
            "provider": provider, "id": model,
            "base_url": os.environ.get("ARGVERIFY_BASE_URL", ""),
            "api_key_present": bool(os.environ.get("ARGVERIFY_API_KEY")),
            "local_model": ollama_info(model) if "localhost" in os.environ.get("ARGVERIFY_BASE_URL", "") else None,
        },
        "limits": {
            "max_output_tokens": int(os.environ.get("ARGVERIFY_MAX_TOKENS", "2048")),
            "reasoning_setting": os.environ.get("ARGVERIFY_REASONING", "none"),
            "timeout_s": float(os.environ.get("ARGVERIFY_TIMEOUT_S", "300")),
            "retries": 0,
            "temperature": "0 where accepted; omitted for GPT-5 family",
        },
        "hardware": {"platform": platform.platform(), "machine": platform.machine(),
                     "python": platform.python_version(),
                     "cpu_count": os.cpu_count()},
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(m, indent=2))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
