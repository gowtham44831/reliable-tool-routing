"""Export per-case AI-verifier traces: exact request, raw response,
parsed findings, final action.

    python scripts/export_ai_traces.py TB-01b TB-03b TB-07b \
        [--results results/argverify_dev_run1/results.json]

Writes docs/argument_verification_ai_traces.md. The request body is
reconstructed deterministically from PROMPT + _public_case_dict (the same
code path the verifier uses), so it is byte-identical to what was sent
in the referenced run provided llm.py's prompt is unchanged (prompt_sha
is recorded to verify that).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tool_routing.argverify.llm import PROMPT, _public_case_dict
from tool_routing.argverify.schema import FIXTURE_PATH, load_cases


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_ids", nargs="+")
    ap.add_argument("--results", default="results/argverify_dev_run1/results.json")
    ap.add_argument("--out", default="docs/argument_verification_ai_traces.md")
    args = ap.parse_args()

    results = json.loads(Path(args.results).read_text())
    ai = next(r for r in results if r["method"] == "ai")
    rows = {r["case_id"]: r for r in ai["rows"]}
    cases = {c.case_id: c for c in load_cases(FIXTURE_PATH)}

    doc = ["# AI verifier — case traces (run argverify_dev_run1)", "",
           "Provider: local Ollama, OpenAI-compatible `/v1/chat/completions`.",
           "Model: `qwen3:0.6b` (Q4_K_M, 751M params, 40960-token context).",
           "Settings in this run: `temperature=0`, `think=false` (an",
           "Ollama-native field possibly ignored on the OpenAI-compat",
           "endpoint), **no `max_tokens` bound**, timeout 300 s,",
           "no retries (single attempt per case).", ""]
    for cid in args.case_ids:
        case, row = cases[cid], rows[cid]
        body = {"model": "qwen3:0.6b",
                "messages": [{"role": "user",
                              "content": PROMPT.format(
                                  case_json=json.dumps(_public_case_dict(case)))}],
                "temperature": 0, "think": False}
        doc += [f"## {cid}  (expected: {row['expected_action']}, "
                f"predicted: {row['pred_action']}, "
                f"latency {row['latency_s']:.1f}s, usage {row.get('usage')})", "",
                "### Request sent", "```json", json.dumps(body, indent=2), "```", "",
                "### Raw response", "```",
                (row.get("raw") or "(empty — no content returned)"), "```", "",
                "### Parsed findings", "```json",
                json.dumps(row["arg_findings"], indent=2), "```", "",
                "### Expected findings", "```json",
                json.dumps(row["expected_findings"], indent=2), "```", "",
                f"### Final decision: `{row['pred_action']}` "
                f"(expected `{row['expected_action']}`)", "",
                f"parse_ok={row.get('parse_ok')}  error={row.get('error')}", ""]
    Path(args.out).write_text("\n".join(doc))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
