"""Provider adapters for the AI verifier comparison (v2 validation).

Three transports, ONE prompt (``llm.PROMPT``, sha recorded), ONE
validator (``llm_v2.validate``), ONE policy (``policy.next_action``):

- ``openai_compat``  OpenAI-compatible chat completions (Ollama, OpenAI)
- ``anthropic``      Anthropic Messages API

Configuration is by environment only; nothing is logged except model id,
settings, raw text, usage, finish reason. Keys are never written.

    ARGVERIFY_PROVIDER      openai_compat | anthropic
    ARGVERIFY_BASE_URL      e.g. http://localhost:11434/v1 | https://api.openai.com/v1
                            | https://api.anthropic.com
    ARGVERIFY_API_KEY
    ARGVERIFY_MODEL         e.g. qwen3:14b | gpt-5.4-2026-03-05 | claude-sonnet-5-5
    ARGVERIFY_MAX_TOKENS    default 2048
    ARGVERIFY_TIMEOUT_S     default 300
    ARGVERIFY_REASONING     provider-specific reasoning control (see below); default "none"

Provider-specific adaptations (recorded in run_config):
- openai_compat/OpenAI GPT-5.x: ``reasoning_effort`` = ARGVERIFY_REASONING
  (``none|low|medium|high|xhigh`` per GPT-5.4 docs; default none).
  ``temperature`` is NOT sent for GPT-5-family models (reasoning models
  reject non-default temperature); it IS sent (0) for Ollama.
- openai_compat/Ollama: ``think: false`` passed (may be ignored on /v1).
- anthropic: ``max_tokens`` required; ``output_config.effort`` =
  ARGVERIFY_REASONING mapped to ``low|medium|high`` (default ``low`` —
  the lowest documented level; thinking is adaptive on 5.5 models and
  cannot be fully disabled through effort alone). ``temperature`` 0.
  Text is taken from the first ``text`` content block; ``stop_reason``
  is recorded as finish_reason.

Retry policy: none (one attempt per case). Transport errors and
HTTP errors are returned as ``verifier_error`` records.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request

from .llm import PROMPT, _parse_json, _public_case_dict
from .llm_v2 import validate
from .policy import missing_required_args, next_action
from .schema import Case

PROMPT_SHA = hashlib.sha256(PROMPT.encode()).hexdigest()[:16]


def _cfg() -> dict:
    return {
        "provider": os.environ.get("ARGVERIFY_PROVIDER", "openai_compat"),
        "base_url": os.environ.get("ARGVERIFY_BASE_URL", "").rstrip("/"),
        "model": os.environ.get("ARGVERIFY_MODEL", ""),
        "max_tokens": int(os.environ.get("ARGVERIFY_MAX_TOKENS", "2048")),
        "timeout_s": float(os.environ.get("ARGVERIFY_TIMEOUT_S", "300")),
        "reasoning": os.environ.get("ARGVERIFY_REASONING", "none"),
        "retries": 0,
        "prompt_sha": PROMPT_SHA,
        "validator": "v2",
    }


def _is_gpt5(model: str) -> bool:
    return model.startswith(("gpt-5", "o1", "o3", "o4"))


def _post(url: str, body: dict, headers: dict, timeout: float) -> tuple[dict | None, str | None, float]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", **headers})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read()), None, time.perf_counter() - t0
    except urllib.error.HTTPError as e:
        # body may contain a provider error message; never contains our key
        try:
            msg = e.read().decode()[:500]
        except Exception:  # noqa: BLE001
            msg = ""
        return None, f"HTTPError {e.code}: {msg}", time.perf_counter() - t0
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}", time.perf_counter() - t0


def _call_openai_compat(prompt: str, cfg: dict, key: str) -> tuple[str, str | None, dict, str | None, float]:
    body: dict = {"model": cfg["model"],
                  "messages": [{"role": "user", "content": prompt}],
                  "max_tokens": cfg["max_tokens"]}
    if _is_gpt5(cfg["model"]):
        if cfg["reasoning"] != "none":
            body["reasoning_effort"] = cfg["reasoning"]
        # GPT-5 family: max_completion_tokens is the accepted name
        body["max_completion_tokens"] = body.pop("max_tokens")
    else:
        body["temperature"] = 0
        body["think"] = False
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    resp, err, lat = _post(f"{cfg['base_url']}/chat/completions", body, headers, cfg["timeout_s"])
    if err:
        return "", err, {}, None, lat
    ch = resp["choices"][0]
    return (ch["message"].get("content") or ""), None, resp.get("usage", {}), ch.get("finish_reason"), lat


def _call_anthropic(prompt: str, cfg: dict, key: str) -> tuple[str, str | None, dict, str | None, float]:
    effort = {"none": "low", "low": "low", "medium": "medium", "high": "high"}.get(cfg["reasoning"], "low")
    body = {"model": cfg["model"], "max_tokens": cfg["max_tokens"],
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {"effort": effort}}
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    resp, err, lat = _post(f"{cfg['base_url']}/v1/messages", body, headers, cfg["timeout_s"])
    if err:
        return "", err, {}, None, lat
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    u = resp.get("usage", {})
    usage = {"prompt_tokens": u.get("input_tokens"), "completion_tokens": u.get("output_tokens"),
             "total_tokens": (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0),
             "raw_usage": u}
    return text, None, usage, resp.get("stop_reason"), lat


def ai_verifier_provider(case: Case) -> dict | None:
    cfg = _cfg()
    key = os.environ.get("ARGVERIFY_API_KEY", "")
    if not cfg["base_url"] or not cfg["model"]:
        return None
    prompt = PROMPT.format(case_json=json.dumps(_public_case_dict(case)))
    call = _call_anthropic if cfg["provider"] == "anthropic" else _call_openai_compat
    text, err, usage, finish, lat = call(prompt, cfg, key)
    base = {"latency_s": lat, "model": cfg["model"], "usage": usage,
            "finish_reason": finish, "raw": text, "config": cfg,
            "request_prompt_sha": PROMPT_SHA}
    if err:
        return {**base, "findings": {}, "details": {}, "action": "verifier_error",
                "error": err, "parse_ok": False}
    parsed = _parse_json(text)
    findings, verr = validate(case, text, parsed)
    if verr:
        return {**base, "findings": {}, "action": "verifier_error", "parse_ok": False,
                "error": f"validation: {verr}",
                "details": {"validation_error": verr,
                            "model_declared_action": str(parsed.get("next_action")) if isinstance(parsed, dict) else None}}
    reasons = parsed.get("reasons", {})
    details = reasons if isinstance(reasons, dict) else {"_": str(reasons)}
    details["model_declared_action"] = str(parsed.get("next_action"))
    return {**base, "findings": findings, "details": details, "parse_ok": True,
            "action": next_action(case, findings, missing_required_args(case))}
