"""Paper-based reimplementation of a ToolMinimize-style minimizer.

NOT a reproduction of the authors' system: no artifact is published;
this implements the described operations (removal, generalization,
substitution, truncation), schema annotations (minimum_necessary),
and a fail-prompt-style escalation — deterministically, no LLM.
Deviations from the paper: no PSD classifier (private fields are
declared by the experiment), no content-aware LLM layer (an optional
deterministic content-strip stands in), no PC metric.

Ladder for location generalization: exact -> ~1.1km grid ->
~5.6km grid -> city centroid. The schema annotation
`minimum_necessary` asserts the granularity the tool needs; the
minimizer jumps straight to the coarsest permitted level — which is
exactly the paper's 4/20 end-to-end failure mechanism (annotation
exists, task needed finer).
"""

GRID1, GRID5, CITY = "grid_1km", "grid_5km", "city"
CITY_CENTER = (40.03, -74.02)


def _round_grid(v: float, step_deg: float) -> float:
    return round(v / step_deg) * step_deg


def generalize_point(lat, lon, level):
    if level == GRID1:
        return _round_grid(lat, 0.01), _round_grid(lon, 0.01)
    if level == GRID5:
        return _round_grid(lat, 0.05), _round_grid(lon, 0.05)
    if level == CITY:
        return CITY_CENTER
    return lat, lon


def minimize(call: dict, schema: dict, *, granularity: str,
             escalate_on_sensitive_required: bool = True):
    """call: {"tool":..., "args":{...}, "private_fields": [...]}.
    Returns {"call": rewritten_or_None, "status": dispatch|escalate,
             "ops": [...], "disclosed": [field names still sent]}.

    Mitigations included (per paper): removal of optional PSD fields,
    annotation-guided generalization (coarsest permitted), and
    escalation instead of dispatch when a REQUIRED sensitive field
    cannot be safely rewritten — the fail-prompt analog, NOT a
    successful completion."""
    args = dict(call["args"])
    ops, removed = [], []
    # Op 1 — removal: optional private fields never needed.
    for p in schema["parameters"]:
        spec = schema["parameters"][p]
        if not spec["required"] and p in call["private_fields"] \
                and p in args:
            removed.append(p)
            del args[p]
            ops.append(f"remove:{p}")
    # Op 2 — generalization of the required location payload.
    g_lat, g_lon = generalize_point(args["lat"], args["lon"],
                                    granularity)
    if (g_lat, g_lon) != (args["lat"], args["lon"]):
        ops.append(f"generalize:lat,lon->{granularity}")
    args["lat"], args["lon"] = g_lat, g_lon
    # Escalation analog: sensitive required payload coarsened — if the
    # payload itself IS the sensitive item (precise-origin tasks),
    # flag for confirmation rather than silently dispatch.
    status = "dispatch"
    if escalate_on_sensitive_required and "lat" in \
            call["private_fields"] and granularity != "exact" \
            and call.get("exact_required"):
        status = "escalate"
        ops.append("fail_prompt:exact-origin-required")
    return {"call": {"tool": call["tool"], "args": args},
            "status": status, "ops": ops,
            "disclosed": sorted(args),
            "removed": removed}


def disclosed_private(call, private_fields) -> list[str]:
    """Which declared-private inputs still appear in the call args."""
    return sorted(f for f in private_fields
                  if f in call["args"])
