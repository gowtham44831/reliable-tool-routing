"""Sibling url_fetch interception gateway (``url-gw-1.0``).

Scoped prototype for the ShadowLeak mechanism (INC-04): an agent-
proposed outbound URL request carrying encoded data in the query
string. ``disclosure.py`` and ``min_disclosure.py`` are frozen and
untouched; this module reuses their authorization helpers where the
semantics apply.

This is content matching, not full provenance tracking: decoded URL
segments are exact-matched against values present in
``retrieved_content`` and attributed to fields via the application-
supplied ``field_metadata`` provenance strings. The metadata is an
assumption, disclosed as such — no evaluator-only labels are used.

Fetch policy (explicit; NOT claimed identical to the email/POST rules):

- F1  ``url_fetch`` calls are inspected before dispatch; the checked
      object is the actual serialized URL.
- F2  Calls to hosts not in ``policy["fetch_allowlist"]`` are denied.
      The allowlist is a NEW rule (the R4 ``http_allowlist`` governs
      only ``http_post`` credentials and is not silently reused).
- F3  An allowlisted host alone does NOT authorize sending protected
      data: every matched protected-class field still needs R3-style
      authorization (permission record, destination==owner, or a
      verified owner grant turn). Deny-wins (R6) still applies.
- F4  Matched values without application-supplied metadata never
      default to safe — unresolved, per R7.
- F5  Unsupported encodings and uncertain/ambiguous matches are
      recorded explicitly; a fetch whose payload could not be fully
      accounted for is denied unless empty or fully explained.

Dispatch is LOCAL ONLY (127.0.0.1 / localhost mock destinations) and
redirects are disabled.
"""

from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from tool_routing.argverify.disclosure import (
    PROTECTED_CLASSES,
    _grant_from_turn,
    _record_covers,
    action_fingerprint,
)

URL_GW_VERSION = "url-gw-1.1"
LEGACY_GW_VERSION = "url-gw-1.0"

FETCH_POLICY_TEXT = [
    "F1 url_fetch calls are inspected before dispatch on the serialized URL.",
    "F2 calls to hosts not in fetch_allowlist are denied (fetch-specific rule).",
    "F3 allowlisted host alone does not authorize protected data: matched "
    "protected-class fields need R3-style authorization; deny-wins applies.",
    "F4 matched values without metadata never default to safe (R7 analogue).",
    "F5 (v1.1) every in-scope carrier is accounted for INDEPENDENTLY: each "
    "query param's extracted atoms (decoded value, or each member of a "
    "decoded JSON object/array; else the raw value) must every match a "
    "retrieved value. A match in one parameter never waives coverage of "
    "another; planner `payload_fields` declarations are hints, not proof "
    "of coverage. Path segments remain exempt (routing structure — a "
    "recorded coverage limitation, not a safety claim). Empty values "
    "carry nothing and are accounted trivially. Unsupported encodings "
    "and uncertain matches are recorded; unaccounted content is denied.",
    "F5 (v1.0, legacy) an unaccounted carrier was suppressed whenever a "
    "planner-declared field also matched — a coverage defect: one "
    "authorized field laundered arbitrary extra carriers per call "
    "(docs/counterexample_decision.md, results/f5_coverage_repro).",
]

# ---------------------------------------------------------------------------
# Bounds (prototype)
# ---------------------------------------------------------------------------

MAX_URL_LENGTH = 4096
MAX_QUERY_PARAMS = 32
MAX_PATH_SEGMENTS = 16
MAX_CANDIDATE_BYTES = 4096
MAX_DECODED_BYTES = 4096

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

BLOCKING = {
    "fetch_host_offlist",
    "no_authorization",
    "unresolved_destination",
    "unresolved_owner",
    "credential_fetch_offlist",
    "unaccounted_payload",
    "unparseable_url",
    "oversized_url",
    "policy_conflict",
}


# ---------------------------------------------------------------------------
# Bounded decoding + exact content matching
# ---------------------------------------------------------------------------


def _try_b64(s: str) -> tuple[str | None, str | None]:
    """Strict standard- and urlsafe-base64 decode. Returns (decoded_text,
    alphabet) or (None, reason)."""
    if len(s) > MAX_CANDIDATE_BYTES or len(s) < 8 or len(s) % 4 != 0:
        return None, "not-base64-shaped"
    for name, altchars in (("base64", None), ("base64url", b"-_")):
        try:
            raw = base64.b64decode(s.encode(), altchars=altchars, validate=True)
        except Exception:
            continue
        if not raw or len(raw) > MAX_DECODED_BYTES:
            continue
        try:
            return raw.decode("utf-8"), name
        except UnicodeDecodeError:
            continue
    return None, "no-supported-encoding"


def decode_url_payload(url: str) -> dict:
    """Bounded URL decode: query values and path segments are candidate
    carriers; each is tried raw and strict-base64. Every step is logged."""
    log: list[dict] = []
    candidates: list[dict] = []
    errors: list[str] = []

    if len(url) > MAX_URL_LENGTH:
        return {"candidates": [], "decode_log": log,
                "errors": [f"oversized_url ({len(url)} > {MAX_URL_LENGTH})"],
                "parsed": None}
    try:
        parts = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if len(query) > MAX_QUERY_PARAMS:
            errors.append(f"too many query params ({len(query)})")
            query = query[:MAX_QUERY_PARAMS]
        segments = [s for s in parts.path.split("/") if s][:MAX_PATH_SEGMENTS]
    except Exception as e:  # noqa: BLE001 - record, do not crash the gate
        return {"candidates": [], "decode_log": log,
                "errors": [f"unparseable_url: {e}"], "parsed": None}

    raws = [(k, v, "query") for k, v in query]
    raws += [(f"path.{i}", s, "path") for i, s in enumerate(segments)]
    parsed = {"scheme": parts.scheme, "host": parts.hostname or "",
              "port": parts.port, "path": parts.path}
    for key, raw, where in raws:
        cand = {"key": key, "where": where, "raw": raw,
                "decoded": None, "steps": ["url_param_raw"]}
        text, how = _try_b64(raw)
        if text is not None:
            cand["decoded"] = text
            cand["steps"].append(f"{how}_decode")
        elif how == "no-supported-encoding":
            cand["steps"].append("decode_unsupported")
        log.append({"key": key, "where": where, "steps": cand["steps"]})
        candidates.append(cand)
    return {"candidates": candidates, "decode_log": log,
            "errors": errors, "parsed": parsed}


def retrieved_value_index(view: dict) -> dict[str, list[str]]:
    """value -> [field ids] index over retrieved_content, attributed via
    application-supplied field_metadata provenance strings. Values with no
    metadata map to the marker ``<unlabeled>`` — uncertain, never safe."""
    idx: dict[str, list[str]] = {}
    outputs = {r["call_id"]: r.get("output", {})
               for r in view.get("retrieved_content", [])}
    labeled_keys: set[tuple[str, str]] = set()
    for fid, meta in view.get("field_metadata", {}).items():
        prov = meta.get("provenance", "")
        if not prov.startswith("tool."):
            continue
        _, cid, _, out_key = prov.split(".", 3)
        val = outputs.get(cid, {}).get(out_key)
        if val is not None:
            labeled_keys.add((cid, out_key))
            idx.setdefault(str(val), []).append(fid)
    for cid, out in outputs.items():
        for out_key, val in out.items():
            if (cid, out_key) not in labeled_keys:
                idx.setdefault(str(val), []).append(f"<unlabeled:{cid}.{out_key}>")
    return idx


def match_candidates(candidates: list[dict], vidx: dict[str, list[str]]) -> list[dict]:
    """Exact-match each candidate's decoded (else raw) text against the
    retrieved-value index. A decoded payload may be a serialized object —
    its members are also matched individually. No fuzzy matching."""
    matches: list[dict] = []
    for cand in candidates:
        texts = [t for t in (cand["decoded"], cand["raw"]) if t]
        if cand["decoded"]:
            try:
                obj = json.loads(cand["decoded"])
                if isinstance(obj, dict):
                    texts += [str(v) for v in obj.values()]
                elif isinstance(obj, list):
                    texts += [str(v) for v in obj]
            except (json.JSONDecodeError, TypeError):
                pass
        seen: set[tuple[str, str]] = set()
        for text in texts:
            for fid in vidx.get(text, []):
                if (text, fid) in seen:
                    continue
                seen.add((text, fid))
                matches.append({
                    "carrier": cand["key"], "where": cand["where"],
                    "matched_value": text, "field_id": fid,
                    "uncertain": fid.startswith("<unlabeled:") or len(vidx[text]) > 1,
                    "ambiguous_with": [f for f in vidx[text] if f != fid],
                })
    return matches


# ---------------------------------------------------------------------------
# Enforcement
# ---------------------------------------------------------------------------


def _carrier_atoms(cand: dict) -> list[str]:
    """The atomic strings a carrier transmits, per the strict-accounting
    definition: if the decoded text is a JSON object/array, its member
    values are the atoms (the serialized wrapper is structure); elif a
    decode succeeded, the decoded text is the single atom; otherwise the
    raw param value. Empty raw values carry nothing."""
    if cand["raw"] == "":
        return []
    if cand["decoded"]:
        try:
            obj = json.loads(cand["decoded"])
            if isinstance(obj, dict):
                return [str(v) for v in obj.values()]
            if isinstance(obj, list):
                return [str(v) for v in obj]
        except (json.JSONDecodeError, TypeError):
            pass
        return [cand["decoded"]]
    return [cand["raw"]]


def check_fetch_call(view: dict, clock: str, policy: dict,
                     f5_mode: str = "strict") -> dict:
    """F1–F5 over the gateway view. Sees view + clock + policy only — no
    evaluator_truth. Returns execution decision plus the full evidence
    trail (decoded candidates, matches, findings).

    f5_mode: "strict" (url-gw-1.1) — every non-path carrier's atoms must
    each match a retrieved value; declarations never waive coverage.
    "legacy" (url-gw-1.0) — reproduces the frozen evaluated behavior
    where a declared matching field suppressed unaccounted_payload."""
    call = view["planner_call"]
    if call["tool"] != "url_fetch":
        return {"execution": "gateway_error", "reason": f"not url_fetch: {call['tool']}",
                "findings": [], "matches": [], "decode_log": [], "defects": []}
    url = call["arguments"].get("url", "")
    purpose = call.get("stated_purpose", "")
    decoded = decode_url_payload(url)
    findings: list[dict] = []
    defects: list[dict] = []
    if decoded["parsed"] is None:
        tag = "oversized_url" if "oversized" in (decoded["errors"] or [""])[0] \
            else "unparseable_url"
        findings.append({"field": "_url", "finding": tag,
                         "note": "; ".join(decoded["errors"])})
        return {"execution": "block", "findings": findings, "matches": [],
                "decode_log": decoded["decode_log"], "defects": defects,
                "destination": None}
    host = decoded["parsed"]["host"]
    entry = view.get("directory", {}).get(host)
    dest_principal = entry["principal"] if entry else None
    dest_class = entry["class"] if entry else "external_unknown"
    dest = {"host": host, "principal": dest_principal, "class": dest_class}

    # F2: fetch-specific allowlist (NEW rule — not the R4 http_allowlist)
    allowlist = policy.get("fetch_allowlist", [])
    if host not in allowlist:
        findings.append({"field": "_host", "finding": "fetch_host_offlist",
                         "note": f"{host} not in fetch_allowlist (F2)"})

    vidx = retrieved_value_index(view)
    matches = match_candidates(decoded["candidates"], vidx)
    meta_all = view.get("field_metadata", {})
    allowed_fields: set[str] = set()
    matched_ids: set[str] = set()
    for m in matches:
        fid = m["field_id"]
        matched_ids.add(fid)
        if m["uncertain"]:
            # F4 / recorded uncertainty; unlabeled values get the R7
            # analogue below, ambiguous ones are only recorded.
            if fid.startswith("<unlabeled:"):
                findings.append({"field": fid, "finding": "unresolved_owner",
                                 "note": "matched value has no metadata (F4/R7)"})
                continue
        meta = meta_all.get(fid)
        owner = meta["owner"] if meta else None
        fclass = meta["class"] if meta else None
        records = view.get("permission_records", [])
        allows = [r for r in records if r.get("effect", "allow") == "allow"
                  and _record_covers(r, fid, owner, dest_principal, purpose, clock, view)]
        denies = [r for r in records if r.get("effect") == "deny"
                  and _record_covers(r, fid, owner, dest_principal, purpose, clock, view)]
        if denies:
            findings.append({"field": fid, "finding": "policy_conflict",
                             "note": f"deny record {denies[0]['auth_id']} wins (F3/R6)"})
            continue
        if meta is None:
            findings.append({"field": fid, "finding": "unresolved_owner",
                             "note": "no metadata, no covering record (F4/R7)"})
            continue
        permitted = False
        if fclass == "public":
            permitted = True
        elif fclass == "internal":
            permitted = dest_class.startswith("internal") or bool(allows)
        elif fclass in PROTECTED_CLASSES and dest_principal is not None:
            owner_turn = _grant_from_turn(view, owner, dest_principal, purpose) is not None
            permitted = dest_principal == owner or bool(allows) or owner_turn
        if not permitted:
            # F3: protected data needs authorization REGARDLESS of host
            finding = ("no_authorization" if dest_principal is not None
                       else "unresolved_destination")
            findings.append({"field": fid, "finding": finding, "owner": owner,
                             "class": fclass, "dest": dest})
        else:
            allowed_fields.add(fid)
            findings.append({"field": fid, "finding": "permitted",
                             "owner": owner, "class": fclass})

    # F5: payload accounting. strict (url-gw-1.1): every non-path
    # carrier's atoms are checked INDEPENDENTLY — a match elsewhere or
    # a planner declaration never waives coverage. legacy (url-gw-1.0):
    # suppressed when a declared field matched (coverage defect).
    declared = set(call.get("payload_fields", []))
    unsupported = [c["key"] for c in decoded["candidates"]
                   if "decode_unsupported" in c["steps"]]
    if unsupported:
        defects.append({"type": "unsupported_encodings", "carriers": unsupported})
    if f5_mode == "strict":
        vidx_values = set(vidx)
        unaccounted = []
        for c in decoded["candidates"]:
            if c["key"].startswith("path."):
                continue
            missing = [a for a in _carrier_atoms(c) if a not in vidx_values]
            if missing:
                unaccounted.append((c["key"], missing))
        if unaccounted:
            findings.append({
                "field": "_payload", "finding": "unaccounted_payload",
                "note": "carriers with unmatched atoms (F5 strict): "
                        + "; ".join(f"{k} -> {v}" for k, v in unaccounted)})
    else:
        carriers_with_matches = {m["carrier"] for m in matches}
        unaccounted = [c["key"] for c in decoded["candidates"]
                       if c["key"] not in carriers_with_matches
                       and not c["key"].startswith("path.")]
        if unaccounted and not (declared & matched_ids):
            findings.append({"field": "_payload", "finding": "unaccounted_payload",
                             "note": f"carriers {unaccounted} matched nothing "
                                     f"in retrieved content (F5)"})
    # planner-declared fields vs matched reality — claims are untrusted
    for fid in declared - matched_ids:
        defects.append({"field": fid, "type": "declared_field_not_in_url"})
    for fid in matched_ids - declared:
        defects.append({"field": fid, "type": "undeclared_field_in_url"})

    blocked = [f for f in findings if f["finding"] in BLOCKING]
    return {
        "execution": "block" if blocked else "allow",
        "url": url, "destination": dest,
        "decode_log": decoded["decode_log"],
        "decode_errors": decoded["errors"],
        "matches": matches, "findings": findings, "defects": defects,
        "fingerprint": action_fingerprint(
            call, LEGACY_GW_VERSION if f5_mode == "legacy"
            else URL_GW_VERSION,
            view.get("permission_records", [])),
    }


# ---------------------------------------------------------------------------
# Local mock destination + redirect-disabled dispatch
# ---------------------------------------------------------------------------


@dataclass
class LocalFetchDestination:
    """In-memory mock fetch sink; mirrors MockDestinations' contract for
    the fetch channel. ``received`` is ground truth for what left."""
    received: list[dict] = field(default_factory=list)

    def record(self, url: str) -> None:
        self.received.append({"url": url})


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # redirects disabled for this prototype


_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirect())


def dispatch_fetch(url: str, sink: LocalFetchDestination | None = None,
                   timeout: float = 5.0) -> dict:
    """Issue the fetch to a LOCAL mock destination only. Redirects are
    disabled; non-local hosts are refused. Records the serialized URL in
    ``sink`` exactly as sent."""
    host = urllib.parse.urlsplit(url).hostname or ""
    if host not in LOCAL_HOSTS:
        return {"sent": False, "reason": f"non-local host refused: {host}"}
    if sink is not None:
        sink.record(url)
    try:
        with _NO_REDIRECT_OPENER.open(url, timeout=timeout) as resp:
            return {"sent": True, "status": resp.status, "url_sent": url}
    except urllib.error.HTTPError as e:
        if e.code in (301, 302, 303, 307, 308):
            return {"sent": False, "reason": f"redirect refused ({e.code})"}
        return {"sent": True, "status": e.code, "url_sent": url}
    except urllib.error.URLError as e:
        return {"sent": False, "reason": f"fetch failed: {e.reason}"}
