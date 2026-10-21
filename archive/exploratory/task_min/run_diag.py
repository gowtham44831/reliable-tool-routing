"""Diagnostic comparison — task-preserving minimization feasibility.

Arms:
  A-ORIG    original request executed locally = utility reference.
  B-MIN     reimplemented minimizer (annotations + fail-prompt
            escalation); dispatches whatever it emits.
  C-CHECK   B + task-preservation check: the REWRITTEN call is
            executed on the local backend before dispatch and its
            result set is verified against the declared machine-
            checkable constraints (evaluated at the TRUE private
            origin, which never leaves the machine). On failure ->
            escalate (blocked), never dispatch a broken rewrite.

Dependency stated: the check requires a locally evaluable model of
the backend (here: the actual local dataset). Cost/limits are in
REPORT.md.

  python archive/exploratory/task_min/run_diag.py
"""

import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dataset import (TOOL_SCHEMA, USER_PRIVATE, _hav_km,
                     location_search)                          # noqa: E402
from minimizer import (generalize_point, minimize,
                      disclosed_private)                       # noqa: E402
from tasks import TASKS                                        # noqa: E402

OUT = Path(__file__).parent / "results"

# Service-side cap: a real backend limits query radius. When the
# required inflation exceeds it, the superset guarantee cannot be
# made and the correct outcome is escalation (BLOCKED, not success).
SERVICE_MAX_RADIUS_KM = 6.0
# Generalization error bound per granularity level (km): half the
# grid-cell diagonal; city = worst-case distance to city center.
GRID_ERR = {"exact": 0.0, "grid_1km": math.sqrt(2) * 0.01 * 111 / 2,
            "grid_5km": math.sqrt(2) * 0.05 * 111 / 2, "city": 4.5}


def satisfies(results, constraints, true_lat, true_lon):
    """Constraint check on ACTUAL results — distance measured from the
    TRUE private origin (local only), not the disclosed one."""
    if not results:
        return False
    ok = True
    for r in results:
        # dist_km was computed vs the (possibly coarsened) query point;
        # re-derive truth distance is not possible from the result
        # alone — the check instead re-executes the true-constraint
        # query locally. Here we verify attribute-level constraints.
        if constraints.get("wheelchair") and not r["wheelchair"]:
            ok = False
        if "max_price" in constraints and r["price"] > \
                constraints["max_price"]:
            ok = False
    return ok


def task_preserving(rewritten_args, constraints, true_lat, true_lon):
    """The candidate check: (i) the rewritten query returns at least
    one constraint-satisfying result, and (ii) the result set covers
    the utility reference set R* — the results the ORIGINAL request
    returns locally under the true constraints. R* is computed
    locally; the original private request is never sent externally."""
    ref = location_search(category=constraints["category"],
                          lat=true_lat, lon=true_lon,
                          radius_km=constraints["max_dist_km"],
                          wheelchair_required=constraints.get(
                              "wheelchair", False),
                          max_price=constraints.get("max_price"))
    if not ref:
        return {"ok": False, "reason": "no_reference_results",
                "results_satisfy": None, "covers_reference": None,
                "ref_ids": [], "got_ids": [], "missing": []}
    got = location_search(**rewritten_args)
    sat = satisfies(got, constraints, true_lat, true_lon)
    ref_ids = {r["id"] for r in ref}
    got_ids = {r["id"] for r in got}
    return {"ok": sat and ref_ids <= got_ids,
            "results_satisfy": sat,
            "covers_reference": ref_ids <= got_ids,
            "ref_ids": sorted(ref_ids), "got_ids": sorted(got_ids),
            "missing": sorted(ref_ids - got_ids)}


def run_task(task) -> dict:
    row = {"task": task["id"], "exact_required": task["exact_required"]}
    cons = task["constraints"]
    call = dict(task["call"],
              exact_required=task["exact_required"])
    th, tl = USER_PRIVATE["home_lat"], USER_PRIVATE["home_lon"]

    # --- A: utility reference (original, local execution) ---
    t0 = time.perf_counter()
    ref = location_search(**{k: v for k, v in call["args"].items()
                             if k not in ("user_name", "note")})
    row["orig"] = {"results": len(ref), "ids": [r["id"] for r in ref],
                   "disclosed_private": disclosed_private(
                       call, call["private_fields"]),
                   "latency_ms": round((time.perf_counter() - t0)
                                       * 1e3, 3)}

    # --- B: minimizer alone ---
    t0 = time.perf_counter()
    m = minimize(call, TOOL_SCHEMA, granularity=task["granularity"])
    if m["status"] == "dispatch":
        got = location_search(**m["call"]["args"])
        chk = task_preserving(m["call"]["args"], cons, th, tl)
        b = {"status": "dispatched", "results": len(got),
             "constraints_ok": chk["results_satisfy"],
             "covers_reference": chk["covers_reference"],
             "missing_ref_ids": chk["missing"]}
    else:
        b = {"status": "escalated", "results": 0,
             "constraints_ok": None, "covers_reference": None,
             "missing_ref_ids": []}
    b.update({"ops": m["ops"],
              "disclosed_private": disclosed_private(
                  m["call"], call["private_fields"]),
              "latency_ms": round((time.perf_counter() - t0) * 1e3, 3)})
    row["min_only"] = b

    # --- C: minimizer + task-preservation check ---
    t0 = time.perf_counter()
    m2 = minimize(call, TOOL_SCHEMA, granularity=task["granularity"])
    if m2["status"] == "dispatch":
        chk = task_preserving(m2["call"]["args"], cons, th, tl)
        if chk["ok"]:
            got = location_search(**m2["call"]["args"])
            c = {"status": "dispatched", "results": len(got),
                 "constraints_ok": True,
                 "covers_reference": True}
        else:
            c = {"status": "escalated_by_check", "results": 0,
                 "constraints_ok": chk["results_satisfy"],
                 "covers_reference": chk["covers_reference"],
                 "missing_ref_ids": chk["missing"]}
    else:
        c = {"status": "escalated", "results": 0,
             "constraints_ok": None, "covers_reference": None}
    c.update({"ops": m2["ops"],
              "disclosed_private": disclosed_private(
                  m2["call"], call["private_fields"]),
              "latency_ms": round((time.perf_counter() - t0) * 1e3, 3)})
    row["min_plus_check"] = c

    # --- D: superset rewrite + local refilter ---
    # Rewrite = coarsen point AND inflate radius by the generalization
    # error bound, so the returned set provably contains every
    # constraint-satisfying item; the TRUE constraints are then applied
    # locally. Exact task answer, coarse disclosure — no local replica
    # of the tool data needed for the guarantee (geometry only).
    t0 = time.perf_counter()
    g = task["granularity"]
    g_lat, g_lon = generalize_point(
        call["args"]["lat"], call["args"]["lon"], g)
    err = GRID_ERR[g] + _hav_km(call["args"]["lat"],
                              call["args"]["lon"], g_lat, g_lon)
    inflated = cons["max_dist_km"] + err
    if inflated > SERVICE_MAX_RADIUS_KM:
        d = {"status": "escalated_superset_infeasible", "results": 0,
             "needed_radius": round(inflated, 2),
             "service_cap": SERVICE_MAX_RADIUS_KM}
    else:
        args = {"category": cons["category"], "lat": g_lat,
                "lon": g_lon, "radius_km": inflated}
        raw = location_search(**args)
        final = [r for r in raw
                 if _hav_km(th, tl, r["lat"], r["lon"])
                 <= cons["max_dist_km"]
                 and (not cons.get("wheelchair") or r["wheelchair"])
                 and r["price"] <= cons.get("max_price", math.inf)]
        d = {"status": "dispatched", "results": len(final),
             "raw_results": len(raw),
             "constraints_ok": True,
             "covers_reference": {r["id"] for r in final}
             >= {x["id"] for x in ref},
             "inflated_radius_km": round(inflated, 2)}
    d.update({"disclosed": sorted(args) if "args" in dir() else [],
              "disclosed_private": (
                  ["lat", "lon"] if d["status"].startswith("dispatched")
                  else []),
              "latency_ms": round((time.perf_counter() - t0) * 1e3, 3)})
    row["superset_refilter"] = d
    return row


def main() -> None:
    rows = [run_task(t) for t in TASKS]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "diag_traces.json").write_text(json.dumps(rows, indent=2))
    for r in rows:
        print(f"{r['task']}: orig={r['orig']['results']} "
              f"| min={r['min_only']['status']}"
              f"(ok={r['min_only']['constraints_ok']}) "
              f"| +check={r['min_plus_check']['status']} "
              f"| superset={r['superset_refilter']['status']}"
              f"(n={r['superset_refilter'].get('results')})")


if __name__ == "__main__":
    main()
