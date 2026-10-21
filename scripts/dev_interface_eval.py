"""Dev-only interface-reliability eval — fictional data, no security
cases. Two frozen contracts (A text schema, B example contract)
compared on identical tasks + identical difficulty. Acceptance
criteria frozen in the fixture BEFORE running. No silent repair —
invalid output is scored invalid.

Run: .venv/bin/python scripts/dev_interface_eval.py
"""

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from run_multistep_pilot import parse_turn  # noqa: E402
from tool_routing.argverify.planner_adapter import (  # noqa: E402
    serialize_structured_call)

FIXTURE = ("src/tool_routing/argverify/fixtures/"
           "interface_dev_cases_v1.json")
OUT = Path("results/interface_dev")


def call(cfg, messages, seed):
    body = {"model": cfg["model"], "messages": messages,
            "stream": False, "think": cfg["think"],
            "options": dict(cfg["options"], seed=seed)}
    req = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read())
    return resp["message"]["content"]


def check_accept(task, parsed, second=None):
    """Score against the frozen 'accept' text per task kind."""
    k = task["kind"]
    if k == "respond_only":
        return parsed.get("action") == "respond"
    if k == "fetch_then_respond":
        return (parsed.get("action") == "fetch" and second is not None
                and second.get("action") == "respond"
                and "green" in json.dumps(second["detail"]).lower())
    if parsed.get("action") != "fetch":
        return False
    try:
        serialize_structured_call(parsed["call"])  # schema validity
    except ValueError:
        return False
    url = parsed["call"].get("base_url", "")
    params = parsed["call"].get("params", {})
    if k == "fetch_empty_params":
        return url == "http://docs.example/index" and params == {}
    if k == "fetch_two_params":
        return (url == "http://docs.example/report"
                and params.get("city") == "Paris"
                and str(params.get("year")) == "2026")
    if k == "fetch_from_material":
        return ("status.example" in url
                and "Ana Rua" in json.dumps(params)
                and "T-42" in json.dumps(params))
    if k == "correct_malformed":
        return url.startswith("http") and "docs.example" in url
    if k == "fetch_base_url_host_only":
        return (url == "https://api.example.net/v1/status"
                and params.get("verbose") is True)
    return False


def run_task(cfg, task, contract_name, schema):
    messages = [{"role": "user", "content":
                 f"You are an agent with access to tools.\n\n{schema}\n\n"
                 f"Task: {task['task']}\n\nMaterial you retrieved:\n"
                 + json.dumps(task["material"])}]
    if "seed_assistant" in task:  # pre-seeded malformed correction
        messages += [{"role": "assistant", "content": task["seed_assistant"]},
                     {"role": "user", "content": task["seed_feedback"]}]
    raw1 = call(cfg, messages, cfg["seed_base"])
    p1 = parse_turn(raw1)
    second = None
    if task["kind"] == "fetch_then_respond" and p1.get("action") == "fetch":
        messages += [{"role": "assistant", "content": raw1},
                     {"role": "user", "content":
                      "Tool result: " + json.dumps(task["tool_reply"])}]
        raw2 = call(cfg, messages, cfg["seed_base"] + 1)
        second = parse_turn(raw2)
        second["raw"] = raw2[:300]
    return {"task": task["task_id"], "contract": contract_name,
            "action": p1.get("action", p1.get("error")),
            "valid": check_accept(task, p1, second),
            "raw": raw1[:300], "turn2": second}


def main():
    fx = json.loads(Path(FIXTURE).read_text())
    cfg = {"model": fx["model"], "options": fx["options"],
           "think": fx["think"], "seed_base": fx["seed_base"]}
    results = []
    for cname, schema in fx["contracts"].items():
        for task in fx["tasks"]:
            results.append(run_task(cfg, task, cname, schema))
    valid = {c: sum(1 for r in results if r["contract"] == c
                    and r["valid"])
             for c in fx["contracts"]}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "traces.json").write_text(json.dumps(results, indent=2))
    print(json.dumps({"valid_per_contract": valid,
                      "criteria": fx["acceptance_criteria_frozen"]},
                     indent=1))
    for r in results:
        print(f"  {r['contract']} {r['task']}: action={r['action']} "
              f"valid={r['valid']}")


if __name__ == "__main__":
    main()
