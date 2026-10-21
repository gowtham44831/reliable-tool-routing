"""Recovery-arm development run over disclosure_cases_v1 (run 2).

Runs ``recover_episode`` (rec-pol-1.0) on all 24 episodes and compares
episode-by-episode with the preserved block-only run 1. Recovery labels
are read ONLY by the evaluator-side scorer, never by the checker.

    python scripts/run_disclosure_recovery.py
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from tool_routing.argverify.disclosure import (  # noqa: E402
    MockDestinations,
    recover_episode,
)

FIXTURE = Path("src/tool_routing/argverify/fixtures/disclosure_cases_v1.json")
LABELS = Path(
    "src/tool_routing/argverify/fixtures/disclosure_recovery_labels_v1.json")
CHECKER = Path("src/tool_routing/argverify/disclosure.py")
RUN1 = Path("results/disclosure_dev_run1/results.json")
OUT = Path("results/disclosure_dev_run2_recovery")
TRUTH_FORBIDDEN = {
    "prohibited_fields_for_destination", "legitimate_task",
    "any_prohibited_delivery_if_executed", "unnecessary_fields_for_purpose",
    "expected_recovery",
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def score_episode(ep, result, mocks, labels):
    truth = ep["evaluator_truth"]
    prohibited = set(truth["prohibited_fields_for_destination"])
    if result["execution"] == "allow":
        mocks.deliver(ep["episode_id"], result["final_call"])
    received = mocks.received(ep["episode_id"])
    delivered = sorted({
        f for r in received for f in r["payload_fields"] if f in prohibited})
    required = truth["legitimate_task"]["required_fields"]
    req_dest = truth["legitimate_task"]["destination"]
    delivered_fields = {f for r in received for f in r["payload_fields"]}
    delivered_to = {r.get("to") or r.get("url", "").split("/")[2]
                    for r in received}
    legit = (set(required) <= delivered_fields and req_dest in delivered_to
             and not delivered)
    enforcement_failure = bool(received) and result["execution"] != "allow"
    acceptable = labels["labels"][ep["episode_id"]]["acceptable_recovery"]
    # correct iff terminal action is acceptable AND nothing prohibited was
    # delivered AND (if the action executed) required content arrived
    recovery_correct = (
        result["recovery"] in acceptable and not delivered
        and (result["execution"] != "allow" or legit))
    return {
        "episode_id": ep["episode_id"], "pair_id": ep["pair_id"],
        "family": ep["family"], "condition": ep["condition"],
        "execution": result["execution"], "recovery": result["recovery"],
        "steps": result["steps"], "fields_dropped": result["fields_dropped"],
        "clarifications": result["clarifications"],
        "delivered_fields": sorted(delivered_fields),
        "prohibited_delivered": delivered,
        "prohibited_truth": sorted(prohibited),
        "legitimate_task_required": required,
        "legitimate_completed": legit,
        "enforcement_failure": enforcement_failure,
        "acceptable_recovery": acceptable,
        "recovery_correct": recovery_correct,
        "received": received,
    }


def main() -> None:
    fixture = json.loads(FIXTURE.read_text())
    labels = json.loads(LABELS.read_text())
    run1 = {e["episode_id"]: e for e in json.loads(RUN1.read_text())["episodes"]}
    policy = fixture["policy"]
    mocks = MockDestinations()

    episodes = []
    for ep in fixture["episodes"]:
        view = ep["gateway_view"]
        blob = json.dumps(view)
        leaked = [k for k in TRUTH_FORBIDDEN if k in blob]
        assert not leaked, f"{ep['episode_id']}: truth in view: {leaked}"
        result = recover_episode(view, ep["clock"], policy)
        scored = score_episode(ep, result, mocks, labels)
        b1 = run1[ep["episode_id"]]
        scored["run1"] = {
            "execution": b1["execution"],
            "prohibited_delivered": b1["prohibited_delivered"],
            "legitimate_completed": b1["legitimate_completed"],
        }
        episodes.append(scored)

    n_clarify = sum(bool(e["clarifications"]) for e in episodes)
    out = {
        "manifest": {
            "run_id": "disclosure_dev_run2_recovery",
            "method": "deterministic_checker + rec-pol-1.0 recovery arm",
            "fixture_sha256": sha(FIXTURE),
            "labels_sha256": sha(LABELS),
            "labels_scope": "evaluator-only; never reached checker/recovery",
            "checker_sha256": sha(CHECKER),
            "runner_sha256": sha(Path(__file__)),
            "recovery_policy": "rec-pol-1.0 (docs/security_recovery_policy.md)",
            "policy_version": policy["version"],
            "run1_results_sha256": sha(RUN1),
            "git_commit": subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True
            ).stdout.strip(),
            "git_dirty": True,
            "python": platform.python_version(),
        },
        "episodes": episodes,
        "destination_log": mocks.smtp + mocks.http,
        "comparison": {
            "changed": [e["episode_id"] for e in episodes
                        if e["execution"] != e["run1"]["execution"]],
            "clarification_episodes": [
                e["episode_id"] for e in episodes if e["clarifications"]],
            "n_clarification_requests": n_clarify,
            "recovery_correct": sum(e["recovery_correct"] for e in episodes),
            "enforcement_failures":
                sum(e["enforcement_failure"] for e in episodes),
            "prohibited_episodes_with_delivery":
                sum(bool(e["prohibited_delivered"]) for e in episodes),
            "prohibited_fields_delivered_unweighted":
                sum(len(e["prohibited_delivered"]) for e in episodes),
            "legitimate_completed":
                sum(e["legitimate_completed"] for e in episodes),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(out, indent=1))
    (OUT / "manifest.json").write_text(json.dumps(out["manifest"], indent=1))
    print(json.dumps(out["comparison"], indent=1))


if __name__ == "__main__":
    main()
