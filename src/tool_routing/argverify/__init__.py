"""Evidence-aware verification of proposed tool arguments (dev prototype).

Research direction "Available Is Not Applicable": given a *proposed* tool
call and the evidence available at the time, decide per-argument whether
the value is supported/missing/contradicted/wrong-entity/unresolved, then
choose an action: proceed / retrieve / clarify / reject_proposed_call.

Nothing here is a benchmark. The fixture in ``fixtures/travel_cases.json``
is 10 paired development cases (20 cases); labels are derived from explicit
per-case rules, not from any verifier's judgment.
"""
