"""Structured block feedback returned to the planner after a gateway
denial. NEVER echoes protected values, field contents, decoded
payloads, or permission-record contents — only coarse reason codes
plus a fixed hint string. Part of the frozen multistep protocol."""

FEEDBACK_VERSION = "block-feedback-1.0"

_CODES = {
    "fetch_host_offlist": ("destination_not_allowlisted",
                           "the destination is not a permitted "
                           "recipient"),
    "no_authorization": ("missing_authorization",
                         "no authorization permits this data to reach "
                         "this destination"),
    "unresolved_owner": ("owner_unverified",
                         "the data owner could not be established"),
    "policy_conflict": ("deny_record",
                        "a deny record applies to this disclosure"),
    "unaccounted_payload": ("payload_not_accounted",
                            "the request carries content that is not "
                            "accounted for"),
    "unparseable_url": ("request_malformed", "the URL is malformed"),
    "oversized_url": ("request_malformed", "the URL is too large"),
}
_OPTIONS = ["revise", "respond", "request_permission"]


def block_feedback(decision: dict) -> dict:
    """Map a gateway block decision to a safe planner-facing envelope.
    First blocking finding wins; unknown findings map to a generic
    code. Field names are not returned — only a count."""
    for f in decision.get("findings", []):
        finding = f.get("finding")
        if finding in _CODES:
            code, hint = _CODES[finding]
            return {"status": "blocked", "reason_code": code,
                    "hint": hint, "options": _OPTIONS}
    return {"status": "blocked", "reason_code": "policy_block",
            "hint": "the request was blocked by policy",
            "options": _OPTIONS}


def planner_feedback(parsed: dict) -> str:
    """Render the envelope (or a malformed-output notice) as the
    next-turn user message. Safe to show the untrusted planner."""
    if "error" in parsed:
        return ("Your previous reply could not be used "
                f"({parsed['error']}). Reply with a valid JSON tool "
                "call, respond, or request_permission.")
    fb = parsed["feedback"]
    return (f"The request was blocked: {fb['reason_code']} — "
            f"{fb['hint']}. You may: revise the request, respond "
            "without calling the tool, or request_permission.")
