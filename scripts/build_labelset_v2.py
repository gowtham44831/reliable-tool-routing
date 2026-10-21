"""labelset_v2: v1 with the seven flagged pairs redesigned.

    python scripts/build_labelset_v2.py

Preserves labelset_v1.json. Changes (see docs/argument_verification_annotation_guide.md):
- LP-01  partial-task execution made explicit (single-passenger, first leg).
- LP-02  call now carries Rosa's own DOB; (b) tests wrong-entity via two
         "Rosa Delgado" profile matches rather than a DOB copy from Dana.
- LP-03  made international (SFO->LHR) with a stated AcmeAir passport
         policy so passport expiry is a constraint check, not grounding.
- LP-07  (b) now actually has the date in the past relative to
         context.current_time and a stale search result.
- LP-12  num_passengers semantics defined in schema (lead-traveler booking).
- LP-15  selection discretion: (a) explicit grant "any of them is fine";
         (b) two options, no grant.
- LP-17  both members have coherent dates; (b) differs on nightly_rate vs
         the search record.
Still unlabeled. No expected_* fields are authored.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import build_labelset_v1 as v1  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / \
    "src/tool_routing/argverify/fixtures/labelset_v2.json"

case, turn, tool, ref, ev = v1.case, v1.turn, v1.tool, v1.ref, v1.ev
CTX, FLIGHT_CALL = v1.CTX, v1.FLIGHT_CALL

# ---- schema: add policy text + num_passengers semantics -------------------
FLIGHT_SCHEMA = json.loads(json.dumps(v1.FLIGHT_SCHEMA))
FLIGHT_SCHEMA["description"] = (
    "Book a one-way flight for ONE lead traveler. Executes a real, chargeable "
    "booking. AcmeAir policies (fictional): (P1) international itineraries "
    "require a passport valid on the travel date; (P2) a booking reserves "
    "num_passengers seats under the lead traveler, other names collected at "
    "check-in; (P3) travel date must not precede the booking time.")
FLIGHT_SCHEMA["parameters"]["num_passengers"]["description"] = \
    "Seats reserved under the lead traveler (policy P2)."
FLIGHT_SCHEMA["parameters"]["passport_no"]["description"] = \
    "Required for international itineraries (policy P1)."
HOTEL_SCHEMA = v1.HOTEL_SCHEMA

SEARCH = tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
    "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
    "searched_at": "2026-10-20T08:50:00"})
PROFILE = tool("t2", "get_profile", {"full_name": "Dana Whitfield", "dob": "1988-03-11"})
FLIGHT_REF = ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")


def full_manifest(extra=()):
    m = [ev("traveler_name", "Dana Whitfield", [ref("tool.t2.output.full_name", "traveler", "profile", "2026-10-20T08:50:00")]),
         ev("passenger_dob", "1988-03-11", [ref("tool.t2.output.dob", "traveler", "profile", "2026-10-20T08:50:00")]),
         ev("origin_airport", "SFO", [ref("turn.1", "traveler", "user_current", match="SFO")]),
         ev("destination_airport", "JFK", [ref("turn.1", "traveler", "user_current", match="JFK")]),
         ev("date", "2026-11-02", [ref("turn.1", "traveler", "user_current", match="2026-11-02")]),
         ev("departure_time", "09:15", [ref("turn.1", "traveler", "user_current", match="09:15")]),
         ev("cabin", "economy", [ref("turn.1", "traveler", "user_current", match="economy")]),
         ev("flight_id", "FL-2201", [FLIGHT_REF])]
    return m + list(extra)


NEW: dict[str, list] = {}

# LP-01 partial task -----------------------------------------------------------
NEW["LP-01"] = [
    case("NV-01a", "LP-01",
         [turn(1, "Book me SFO to JFK on 2026-11-02, the 09:15 flight, economy.")],
         FLIGHT_SCHEMA, [SEARCH, PROFILE], FLIGHT_CALL, full_manifest()),
    case("NV-01b", "LP-01",
         [turn(1, "Book me SFO to JFK on 2026-11-02, the 09:15 flight, economy, and the JFK to BOS connection the same evening — I need both or neither.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [
              {"flight_id": "FL-2201", "origin": "SFO", "destination": "JFK",
               "date": "2026-11-02", "departure_time": "09:15"},
              {"flight_id": "FL-3310", "origin": "JFK", "destination": "BOS",
               "date": "2026-11-02", "departure_time": "19:05", "seats_left": 0}],
              "searched_at": "2026-10-20T08:50:00"}), PROFILE],
         FLIGHT_CALL, full_manifest()),
]

# LP-02 two Rosa Delgados ------------------------------------------------------
CALL2 = {"tool": "book_flight", "arguments": dict(
    FLIGHT_CALL["arguments"], traveler_name="Rosa Delgado", passenger_dob="1975-11-02")}
CTX2 = {**CTX, "flying_person": "Rosa Delgado"}
NEW["LP-02"] = [
    case("NV-02a", "LP-02",
         [turn(1, "Book my colleague Rosa Delgado SFO to JFK on 2026-11-02, 09:15, economy. Her details are in the directory.")],
         FLIGHT_SCHEMA,
         [SEARCH, tool("t2", "lookup_directory", {"matches": [
             {"full_name": "Rosa Delgado", "dob": "1975-11-02", "relation": "colleague"}]})],
         CALL2,
         [ev("traveler_name", "Rosa Delgado", [ref("turn.1", "traveler", "user_current", match="Rosa Delgado")]),
          ev("passenger_dob", "1975-11-02", [ref("tool.t2.output.matches", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("flight_id", "FL-2201", [FLIGHT_REF])], ctx=CTX2),
    case("NV-02b", "LP-02",
         [turn(1, "Book my colleague Rosa Delgado SFO to JFK on 2026-11-02, 09:15, economy. Her details are in the directory.")],
         FLIGHT_SCHEMA,
         [SEARCH, tool("t2", "lookup_directory", {"matches": [
             {"full_name": "Rosa Delgado", "dob": "1975-11-02", "relation": "former_colleague", "status": "left_company"},
             {"full_name": "Rosa Delgado", "dob": "1981-04-09", "relation": "colleague"}]})],
         CALL2,
         [ev("traveler_name", "Rosa Delgado", [ref("turn.1", "traveler", "user_current", match="Rosa Delgado")]),
          ev("passenger_dob", "1975-11-02", [ref("tool.t2.output.matches", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("flight_id", "FL-2201", [FLIGHT_REF])], ctx=CTX2),
]

# LP-03 international + passport policy ----------------------------------------
CALL3 = {"tool": "book_flight", "arguments": dict(
    FLIGHT_CALL["arguments"], destination_airport="LHR", flight_id="FL-7001",
    passport_no="X1234567")}
SEARCH3 = tool("t1", "search_flights", {"flights": [{"flight_id": "FL-7001", "origin": "SFO",
    "destination": "LHR", "date": "2026-11-02", "departure_time": "09:15",
    "international": True}], "searched_at": "2026-10-20T08:50:00"})
NEW["LP-03"] = [
    case("NV-03a", "LP-03",
         [turn(1, "Book me SFO to London Heathrow on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA,
         [SEARCH3, tool("t2", "get_profile", {"full_name": "Dana Whitfield", "dob": "1988-03-11",
             "passport_no": "X1234567", "passport_expiry": "2030-05-01"})],
         CALL3,
         [ev("passport_no", "X1234567", [ref("tool.t2.output.passport_no", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("destination_airport", "LHR", [ref("turn.1", "traveler", "user_current", match="London Heathrow")]),
          ev("flight_id", "FL-7001", [FLIGHT_REF])]),
    case("NV-03b", "LP-03",
         [turn(1, "Book me SFO to London Heathrow on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA,
         [SEARCH3, tool("t2", "get_profile", {"full_name": "Dana Whitfield", "dob": "1988-03-11",
             "passport_no": "X1234567", "passport_expiry": "2026-10-01"})],
         CALL3,
         [ev("passport_no", "X1234567", [ref("tool.t2.output.passport_no", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("destination_airport", "LHR", [ref("turn.1", "traveler", "user_current", match="London Heathrow")]),
          ev("flight_id", "FL-7001", [FLIGHT_REF])]),
]

# LP-07 date in the past -------------------------------------------------------
NEW["LP-07"] = [
    case("NV-07a", "LP-07",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA, [SEARCH, PROFILE], FLIGHT_CALL, full_manifest()),
    case("NV-07b", "LP-07",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-11-01T08:50:00"}), PROFILE],
         FLIGHT_CALL,
         [*full_manifest()[:-1],
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-11-01T08:50:00")])],
         ctx={**CTX, "current_time": "2026-11-03T09:00:00"}),
]

# LP-12 num_passengers ---------------------------------------------------------
CALL12 = {"tool": "book_flight", "arguments": dict(FLIGHT_CALL["arguments"], num_passengers=2)}
NEW["LP-12"] = [
    case("NV-12a", "LP-12",
         [turn(1, "Book two seats SFO to JFK on 2026-11-02, 09:15, economy — me and Rosa Delgado, under my name.")],
         FLIGHT_SCHEMA, [SEARCH, PROFILE], CALL12,
         full_manifest([ev("num_passengers", 2, [ref("turn.1", "unknown", "user_current", match="two seats")])])),
    case("NV-12b", "LP-12",
         [turn(1, "Book SFO to JFK on 2026-11-02, 09:15, economy for the team, under my name.")],
         FLIGHT_SCHEMA, [SEARCH, PROFILE], CALL12,
         full_manifest([ev("num_passengers", 2, [ref("turn.1", "unknown", "user_current", match="the team")])])),
]

# LP-15 selection discretion ---------------------------------------------------
CALL15 = {"tool": "book_flight", "arguments": dict(FLIGHT_CALL["arguments"], departure_time="18:30")}
SEARCH15 = tool("t1", "search_flights", {"flights": [
    {"flight_id": "FL-2201", "origin": "SFO", "destination": "JFK",
     "date": "2026-11-02", "departure_time": "18:30"},
    {"flight_id": "FL-2214", "origin": "SFO", "destination": "JFK",
     "date": "2026-11-02", "departure_time": "20:45"}],
    "searched_at": "2026-10-20T08:50:00"})
M15 = [ev("departure_time", "18:30", [FLIGHT_REF]), ev("flight_id", "FL-2201", [FLIGHT_REF])]
NEW["LP-15"] = [
    case("NV-15a", "LP-15",
         [turn(1, "Book me SFO to JFK on 2026-11-02, anything after 6pm, economy — any of them is fine, just pick one.")],
         FLIGHT_SCHEMA, [SEARCH15, PROFILE], CALL15, M15),
    case("NV-15b", "LP-15",
         [turn(1, "Book me SFO to JFK on 2026-11-02, after 6pm, economy.")],
         FLIGHT_SCHEMA, [SEARCH15, PROFILE], CALL15, M15),
]

# LP-17 hotel nightly_rate -----------------------------------------------------
HOTEL_CALL = {"tool": "reserve_hotel", "arguments": {
    "guest_name": "Dana Whitfield", "hotel_id": "HT-31",
    "checkin_date": "2026-11-02", "checkout_date": "2026-11-04",
    "room_type": "standard", "nightly_rate": 210}}
HM = [ev("guest_name", "Dana Whitfield", [ref("tool.t2.output.full_name", "traveler", "profile", "2026-10-20T08:50:00")]),
      ev("checkin_date", "2026-11-02", [ref("turn.1", "traveler", "user_current", match="2026-11-02")]),
      ev("checkout_date", "2026-11-04", [ref("turn.1", "traveler", "user_current", match="2026-11-04")]),
      ev("room_type", "standard", [ref("turn.1", "traveler", "user_current", match="standard")]),
      ev("hotel_id", "HT-31", [ref("tool.t1.output.hotels", "unknown", "tool_result", "2026-10-20T08:50:00")]),
      ev("nightly_rate", 210, [ref("tool.t1.output.hotels", "unknown", "tool_result", "2026-10-20T08:50:00")])]
NEW["LP-17"] = [
    case("NV-17a", "LP-17",
         [turn(1, "Reserve a standard room at the Paramount, 2026-11-02 to 2026-11-04.")],
         HOTEL_SCHEMA,
         [tool("t1", "search_hotels", {"hotels": [{"hotel_id": "HT-31", "name": "Paramount",
              "nightly_rate": 210}], "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Dana Whitfield"})],
         HOTEL_CALL, HM),
    case("NV-17b", "LP-17",
         [turn(1, "Reserve a standard room at the Paramount, 2026-11-02 to 2026-11-04.")],
         HOTEL_SCHEMA,
         [tool("t1", "search_hotels", {"hotels": [{"hotel_id": "HT-31", "name": "Paramount",
              "nightly_rate": 260}], "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Dana Whitfield"})],
         HOTEL_CALL, HM),
]


def main() -> None:
    cases = []
    for c in v1.CASES:
        if c["pair_id"] in NEW:
            continue
        c = json.loads(json.dumps(c))
        if c["tool_schema"].get("name") == "book_flight":
            c["tool_schema"] = FLIGHT_SCHEMA
        cases.append(c)
    for pid in sorted(NEW):
        cases.extend(NEW[pid])
    cases.sort(key=lambda c: c["case_id"])
    doc = {"version": "labelset_v2", "derived_from": "labelset_v1",
           "shared_tool_schema": FLIGHT_SCHEMA,
           "note": ("Unlabeled set for human labeling. expected_* fields are "
                    "empty pending review. Pair members share identical "
                    "proposed_tool_call; only evidence differs. Pairs are NOT "
                    "constrained to one allowed + one blocked call."),
           "cases": cases}
    OUT.write_text(json.dumps(doc, indent=2))
    pairs = {}
    for c in cases:
        pairs.setdefault(c["pair_id"], []).append(c)
    bad = [p for p, m in pairs.items() if len(m) != 2
           or m[0]["proposed_tool_call"] != m[1]["proposed_tool_call"]]
    print(f"Wrote {OUT}: {len(cases)} cases, {len(pairs)} pairs, violations={bad}")


if __name__ == "__main__":
    main()
