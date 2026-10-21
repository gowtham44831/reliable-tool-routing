"""Prompted AI verifier (configurable, off-the-shelf model; no fine-tuning).

Configuration is entirely via environment variables -- nothing is
hard-coded:

- ``ARGVERIFY_API_KEY``   (required; if absent the method reports not-run)
- ``ARGVERIFY_BASE_URL``  (OpenAI-compatible chat endpoint;
                           default http://localhost:11434/v1 -- Ollama)
- ``ARGVERIFY_MODEL``     (default "llama3.1")
- ``ARGVERIFY_MAX_TOKENS`` (output cap; default 2048)
- ``ARGVERIFY_TIMEOUT_S`` (per-request timeout; default 300)

Retry policy: none. One attempt per case; transport failures are recorded
as error records, and unparseable/empty responses are recorded as
``verifier_error`` -- a malformed response never becomes ``proceed`` or
a fabricated action.

The prompt sends only ``Case.public_view()`` data: conversation, tool
contract, prior tool results, context, the proposed call, and the
planner's claimed evidence manifest. Expected findings, label rules and
explanations are never included.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request
from typing import Any

from .policy import missing_required_args, next_action
from .schema import ACTIONS, FINDINGS, Case

PROMPT = """You are a tool-call VERIFIER. A planner proposes the tool call below.
For each proposed argument decide exactly one finding:
  supported | missing | contradicted | wrong_entity | unresolved

Rules:
- A value is "supported" only if the cited source_reference actually
  resolves to content containing that value. A claim of support without
  a resolvable source is not evidence.
- Person-scoped arguments must refer to the person flying
  (context.flying_person), not the requester or a relative.
- Values older than the contract's validity window are "unresolved".
- Conflicting evidence from the current request overrides stored
  preferences and older turns only where the conversation makes that
  explicit.
- "reject_proposed_call" means this exact call must not execute; it does
  not mean abandoning the user's task.

Then pick next_action: proceed | retrieve | clarify | reject_proposed_call.

Respond ONLY with JSON:
{{"argument_findings": {{"<arg>": "<finding>", ...}},
  "reasons": {{"<arg>": "<one line>"}},
  "next_action": "<action>"}}

CASE (all visible evidence):
{case_json}"""


def _public_case_dict(case: Case) -> dict:
    return {
        "context": case.context,
        "conversation": case.conversation,
        "tool_schema": case.tool_schema,
        "prior_tool_results": case.prior_tool_results,
        "proposed_tool_call": case.proposed_tool_call,
        "claimed_evidence_manifest": [
            {"argument_name": e.argument_name, "proposed_value": e.proposed_value,
             "source_references": [{"ref": s.ref, "entity": s.entity, "tier": s.tier,
                                    "timestamp": s.timestamp, "match": s.match}
                                   for s in e.source_references],
             "transformation_or_default": e.transformation_or_default}
            for e in case.evidence_manifest
        ],
        "missing_required_args": missing_required_args(case),
    }


def configured() -> bool:
    return bool(os.environ.get("ARGVERIFY_API_KEY")) or bool(os.environ.get("ARGVERIFY_BASE_URL"))


def _run_config(model: str, max_tokens: int, timeout: float) -> dict:
    return {"provider": "openai-compatible", "model": model,
            "temperature": 0, "max_tokens": max_tokens,
            "timeout_s": timeout, "retries": 0,
            "prompt_sha": __import__("hashlib").sha256(PROMPT.encode()).hexdigest()[:16]}


def ai_verifier(case: Case, timeout: float | None = None) -> dict | None:
    """Returns None when no endpoint/key is configured (marked not-run).

    Per-case transport failures are recorded as ``error`` records and
    empty/unparseable responses as ``verifier_error`` actions -- neither
    is silently mapped to a real decision.
    """
    base = os.environ.get("ARGVERIFY_BASE_URL", "").rstrip("/")
    key = os.environ.get("ARGVERIFY_API_KEY", "")
    model = os.environ.get("ARGVERIFY_MODEL", "llama3.1")
    if not base:
        return None
    max_tokens = int(os.environ.get("ARGVERIFY_MAX_TOKENS", "2048"))
    timeout = float(os.environ.get("ARGVERIFY_TIMEOUT_S", "300") if timeout is None else timeout)
    config = _run_config(model, max_tokens, timeout)
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": PROMPT.format(case_json=json.dumps(_public_case_dict(case)))}],
        "temperature": 0,
        "max_tokens": max_tokens,
        "think": False,  # Ollama-native field; may be ignored on /v1 compat
    }).encode()
    req = urllib.request.Request(
        f"{base}/chat/completions", data=body,
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            resp = json.loads(r.read())
    except Exception as e:  # noqa: BLE001 - record transport errors as data
        return {"findings": {}, "details": {}, "action": "verifier_error",
                "error": f"{type(e).__name__}: {e}",
                "latency_s": time.perf_counter() - t0, "model": model,
                "usage": {}, "raw": None, "config": config}
    latency = time.perf_counter() - t0
    msg = resp["choices"][0]["message"]
    finish = resp["choices"][0].get("finish_reason")
    text = msg.get("content") or ""
    parsed = _parse_json(text)
    af = parsed.get("argument_findings")
    findings = {k: v for k, v in (af.items() if isinstance(af, dict) else [])
                if isinstance(v, str) and v in FINDINGS}
    action = parsed.get("next_action")
    if not findings:
        return {"findings": {}, "details": {}, "action": "verifier_error",
                "error": f"unparseable/empty response (finish_reason={finish})",
                "parse_ok": False, "finish_reason": finish,
                "latency_s": latency, "model": model,
                "usage": resp.get("usage", {}), "raw": text, "config": config}
    reasons = parsed.get("reasons", {})
    details = reasons if isinstance(reasons, dict) else {"_": str(reasons)}
    details["model_declared_action"] = str(action)
    # Action comes from the SAME policy as the deterministic methods:
    # the model supplies findings; findings -> action is not model-chosen.
    policy_action = next_action(case, findings, missing_required_args(case))
    details["policy_action_from_model_findings"] = policy_action
    return {"findings": findings,
            "details": details,
            "action": policy_action,
            "latency_s": latency, "model": model, "parse_ok": True,
            "finish_reason": finish,
            "usage": resp.get("usage", {}), "raw": text, "config": config}


def _parse_json(text: str) -> dict:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    if text.startswith("```"):
        text = text.split("```")[1].lstrip("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else {}
