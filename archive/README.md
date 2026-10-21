# Archive — exploratory and legacy items

Everything under `archive/` is preserved for provenance but is NOT
part of the current supported path. Frozen experiment artifacts are
NOT here — they remain under `results/` untouched.

## exploratory/

- `task_min/` — task-preserving minimization feasibility study
  (ToolMinimize comparison). CLOSED with a STOP recommendation; kept
  as a bounded engineering component only. See its `REPORT.md`.

## Legacy items (still in-tree, labeled, not archived by move)

- `url-gw-1.0` F5 semantics — preserved inside
  `src/tool_routing/argverify/url_fetch_gateway.py` as
  `f5_mode="legacy"` for reproduction of frozen results. The default
  is the corrected `url-gw-1.1` (`f5_mode="strict"`). See
  `results/f5_coverage_repro/REPORT.md`.
- Earlier disclosure/min-disclosure gateways (`disclosure.py`,
  `min_disclosure.py`) — frozen predecessor implementations; the
  `url_fetch` gateway is the current arm. Do not modify them.
- Exploratory scripts retained at `scripts/` root:
  `run_planner_pilot_v1.py`, `replay_planner_pilot_v2_adapter11.py`,
  `run_url_fetch_isolation.py`, `dev_interface_eval.py`,
  `repro_base_policy_denies_public.py`, `repro_f5_coverage.py`,
  `run_multistep_pilot.py` (v1/v2), `run_camel_component_eval.py`.
  Each writes to its own `results/` subdirectory and is documented
  in `docs/STATUS.md`.
