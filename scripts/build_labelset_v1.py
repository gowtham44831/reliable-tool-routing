"""Build the unlabeled human-labeling fixture: 20 NEW pairs (40 cases).

    python scripts/build_labelset_v1.py

Writes src/tool_routing/argverify/fixtures/labelset_v1.json.

These cases are structurally distinct from the development set — they add
new tools (reserve_hotel, rent_car, buy_event_ticket, change_flight) and
new evidence structures (multi-traveler, document expiry, corporate
policy, duplicates, ambiguous group size). NO expected labels are
authored: this set goes to human labeling first. Pair members share an
identical proposed_tool_call; only the evidence differs.
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / \
    "src/tool_routing/argverify/fixtures/labelset_v1.json"

CTX = {"current_time": "2026-10-20T09:00:00", "profile_authorized": True,
       "requester": "Dana Whitfield", "flying_person": "Dana Whitfield",
       "persons": {"Dana Whitfield": {"dob": "1988-03-11"},
                   "Theo Whitfield": {"dob": "2012-07-30"},
                   "Rosa Delgado": {"dob": "1975-11-02"}}}

FLIGHT_SCHEMA = {
    "name": "book_flight",
    "description": "Book a one-way flight. Executes a real, chargeable booking.",
    "parameters": {
        "traveler_name": {"type": "string", "required": True, "person_scoped": True,
                          "hint": "person_name"},
        "passenger_dob": {"type": "string", "format": "date", "required": True,
                          "person_scoped": True, "hint": "date"},
        "origin_airport": {"type": "string", "required": True, "hint": "airport_code"},
        "destination_airport": {"type": "string", "required": True, "hint": "airport_code"},
        "date": {"type": "string", "format": "date", "required": True, "hint": "date"},
        "departure_time": {"type": "string", "pattern": "^\\d{2}:\\d{2}$",
                           "required": True},
        "cabin": {"type": "string", "required": True,
                  "enum": ["economy", "premium", "business"], "default": "economy",
                  "hint": "enum:cabin"},
        "flight_id": {"type": "string", "required": True, "valid_for_hours": 24},
        "num_bags": {"type": "integer", "default": 0, "hint": "integer"},
        "meal": {"type": "string", "enum": ["standard", "vegetarian", "vegan", "kosher"],
                 "default": "standard", "hint": "enum:meal"},
        "seat": {"type": "string", "enum": ["window", "aisle", "middle"],
                 "hint": "enum:seat"},
        "num_passengers": {"type": "integer", "default": 1, "hint": "integer"},
        "passport_no": {"type": "string", "hint": "string"},
        "loyalty_no": {"type": "string", "hint": "string"},
    }}

HOTEL_SCHEMA = {
    "name": "reserve_hotel",
    "description": "Reserve a hotel room. Chargeable.",
    "parameters": {
        "guest_name": {"type": "string", "required": True, "person_scoped": True,
                       "hint": "person_name"},
        "hotel_id": {"type": "string", "required": True},
        "checkin_date": {"type": "string", "format": "date", "required": True,
                         "hint": "date"},
        "checkout_date": {"type": "string", "format": "date", "required": True,
                          "hint": "date"},
        "room_type": {"type": "string", "required": True,
                      "enum": ["standard", "deluxe", "suite"], "default": "standard",
                      "hint": "enum:room_type"},
        "nightly_rate": {"type": "integer", "required": True, "hint": "integer"},
    }}

CAR_SCHEMA = {
    "name": "rent_car",
    "description": "Reserve a rental car. Chargeable.",
    "parameters": {
        "driver_name": {"type": "string", "required": True, "person_scoped": True,
                        "hint": "person_name"},
        "pickup_location": {"type": "string", "required": True, "hint": "string"},
        "pickup_date": {"type": "string", "format": "date", "required": True,
                        "hint": "date"},
        "dropoff_date": {"type": "string", "format": "date", "required": True,
                         "hint": "date"},
        "car_class": {"type": "string", "required": True,
                      "enum": ["compact", "sedan", "suv"], "default": "compact",
                      "hint": "enum:car_class"},
    }}

TICKET_SCHEMA = {
    "name": "buy_event_ticket",
    "description": "Buy event tickets. Chargeable.",
    "parameters": {
        "buyer_name": {"type": "string", "required": True, "person_scoped": True,
                       "hint": "person_name"},
        "event_id": {"type": "string", "required": True},
        "quantity": {"type": "integer", "required": True, "hint": "integer"},
        "section": {"type": "string", "required": True,
                    "enum": ["floor", "lower", "upper"], "hint": "enum:section"},
    }}

CHANGE_SCHEMA = {
    "name": "change_flight",
    "description": "Change an existing booking.",
    "parameters": {
        "booking_ref": {"type": "string", "required": True},
        "new_date": {"type": "string", "format": "date", "required": True,
                     "hint": "date"},
        "new_departure_time": {"type": "string", "pattern": "^\\d{2}:\\d{2}$",
                               "required": True},
    }}

FLIGHT_CALL = {"tool": "book_flight", "arguments": {
    "traveler_name": "Dana Whitfield", "passenger_dob": "1988-03-11",
    "origin_airport": "SFO", "destination_airport": "JFK",
    "date": "2026-11-02", "departure_time": "09:15",
    "cabin": "economy", "flight_id": "FL-2201"}}


def turn(n, text, speaker="user"):
    return {"turn": n, "speaker": speaker, "text": text}


def tool(call_id, name, output):
    return {"call_id": call_id, "tool": name, "output": output}


def ref(r, entity="unknown", tier="user_current", ts=None, match=None):
    d = {"ref": r, "entity": entity, "tier": tier}
    if ts: d["timestamp"] = ts
    if match: d["match"] = match
    return d


def ev(name, value, refs, transform=None):
    d = {"argument_name": name, "proposed_value": value,
         "source_references": refs}
    if transform: d["transformation_or_default"] = transform
    return d


def case(cid, pair, conv, schema, results, call, manifest, ctx=None):
    return {"case_id": cid, "pair_id": pair, "context": ctx or CTX,
            "conversation": conv, "tool_schema": schema,
            "prior_tool_results": results, "proposed_tool_call": call,
            "evidence_manifest": manifest,
            "label_rules": [], "expected_argument_findings": {},
            "expected_next_action": "", "ground_truth_explanation": "",
            "labels_pending_human_review": True}


CASES = []

# --- LP-01: two-leg request; call covers only the first leg ---------------
CASES += [
    case("NV-01a", "LP-01",
         [turn(1, "Book me SFO to JFK on 2026-11-02, the 09:15 flight, economy — that's all I need.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Dana Whitfield", "dob": "1988-03-11"})],
         FLIGHT_CALL,
         [ev("traveler_name", "Dana Whitfield", [ref("tool.t2.output.full_name", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("passenger_dob", "1988-03-11", [ref("tool.t2.output.dob", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("origin_airport", "SFO", [ref("turn.1", "traveler", "user_current", match="SFO")]),
          ev("destination_airport", "JFK", [ref("turn.1", "traveler", "user_current", match="JFK")]),
          ev("date", "2026-11-02", [ref("turn.1", "traveler", "user_current", match="2026-11-02")]),
          ev("departure_time", "09:15", [ref("turn.1", "traveler", "user_current", match="09:15")]),
          ev("cabin", "economy", [ref("turn.1", "traveler", "user_current", match="economy")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-01b", "LP-01",
         [turn(1, "Book me SFO to JFK on 2026-11-02, the 09:15 flight, economy — and then JFK to BOS later that day.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Dana Whitfield", "dob": "1988-03-11"})],
         FLIGHT_CALL,
         [ev("traveler_name", "Dana Whitfield", [ref("tool.t2.output.full_name", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("passenger_dob", "1988-03-11", [ref("tool.t2.output.dob", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("origin_airport", "SFO", [ref("turn.1", "traveler", "user_current", match="SFO")]),
          ev("destination_airport", "JFK", [ref("turn.1", "traveler", "user_current", match="JFK")]),
          ev("date", "2026-11-02", [ref("turn.1", "traveler", "user_current", match="2026-11-02")]),
          ev("departure_time", "09:15", [ref("turn.1", "traveler", "user_current", match="09:15")]),
          ev("cabin", "economy", [ref("turn.1", "traveler", "user_current", match="economy")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-02: two travelers; DOB copied from wrong person -------------------
CALL2 = dict(FLIGHT_CALL); CALL2 = {"tool": "book_flight", "arguments": dict(
    FLIGHT_CALL["arguments"], traveler_name="Rosa Delgado", passenger_dob="1988-03-11")}
CASES += [
    case("NV-02a", "LP-02",
         [turn(1, "Book my colleague Rosa Delgado SFO to JFK on 2026-11-02, 09:15, economy. Her details are in her profile.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Rosa Delgado", "dob": "1975-11-02"},
               )],
         CALL2,
         [ev("traveler_name", "Rosa Delgado", [ref("turn.1", "traveler", "user_current", match="Rosa Delgado")]),
          ev("passenger_dob", "1988-03-11", [ref("tool.t2.output.dob", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])],
         ctx={**CTX, "flying_person": "Rosa Delgado"}),
    case("NV-02b", "LP-02",
         [turn(1, "Book my colleague Rosa Delgado SFO to JFK on 2026-11-02, 09:15, economy. Use my saved details for the form.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Dana Whitfield", "dob": "1988-03-11"})],
         CALL2,
         [ev("traveler_name", "Rosa Delgado", [ref("turn.1", "traveler", "user_current", match="Rosa Delgado")]),
          ev("passenger_dob", "1988-03-11", [ref("tool.t2.output.dob", "requester", "profile", "2026-10-20T08:50:00")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])],
         ctx={**CTX, "flying_person": "Rosa Delgado"}),
]

# --- LP-03: passport expiry (optional arg present) ------------------------
CALL3 = {"tool": "book_flight", "arguments": dict(
    FLIGHT_CALL["arguments"], passport_no="X1234567")}
CASES += [
    case("NV-03a", "LP-03",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Dana Whitfield", "dob": "1988-03-11",
              "passport_no": "X1234567", "passport_expiry": "2030-05-01"})],
         CALL3,
         [ev("passport_no", "X1234567", [ref("tool.t2.output.passport_no", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-03b", "LP-03",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Dana Whitfield", "dob": "1988-03-11",
              "passport_no": "X1234567", "passport_expiry": "2026-10-01"})],
         CALL3,
         [ev("passport_no", "X1234567", [ref("tool.t2.output.passport_no", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-04: corporate cabin policy cap ------------------------------------
CALL4 = {"tool": "book_flight", "arguments": dict(
    FLIGHT_CALL["arguments"], cabin="business")}
CASES += [
    case("NV-04a", "LP-04",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, business class.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t3", "get_travel_policy", {"max_cabin": "business"})],
         CALL4,
         [ev("cabin", "business", [ref("turn.1", "traveler", "user_current", match="business")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-04b", "LP-04",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, business class.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t3", "get_travel_policy", {"max_cabin": "economy"})],
         CALL4,
         [ev("cabin", "business", [ref("turn.1", "traveler", "user_current", match="business")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-05: two-airport city; confirmation turn vs none --------------------
CALL5 = {"tool": "book_flight", "arguments": dict(
    FLIGHT_CALL["arguments"], origin_airport="DCA", destination_airport="BOS")}
CASES += [
    case("NV-05a", "LP-05",
         [turn(1, "Book Washington to Boston on 2026-11-02, 09:15, economy."),
          turn(2, "I meant Reagan National — DCA, not Dulles.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "DCA",
              "destination": "BOS", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"})],
         CALL5,
         [ev("origin_airport", "DCA", [ref("turn.2", "traveler", "user_current", match="DCA")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-05b", "LP-05",
         [turn(1, "Book Washington to Boston on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [
              {"flight_id": "FL-2201", "origin": "DCA", "destination": "BOS",
               "date": "2026-11-02", "departure_time": "09:15"},
              {"flight_id": "FL-2299", "origin": "IAD", "destination": "BOS",
               "date": "2026-11-02", "departure_time": "09:40"}],
              "searched_at": "2026-10-20T08:50:00"})],
         CALL5,
         [ev("origin_airport", "DCA", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-06: codeshare flight id -------------------------------------------
CALL6 = {"tool": "book_flight", "arguments": dict(FLIGHT_CALL["arguments"], flight_id="UA-8842")}
CASES += [
    case("NV-06a", "LP-06",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy — the United codeshare.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "UA-8842", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15",
              "operated_by": "AcmeAir"}],
              "searched_at": "2026-10-20T08:50:00"})],
         CALL6,
         [ev("flight_id", "UA-8842", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-06b", "LP-06",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy — the United codeshare.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "UA-8842", "origin": "SFO",
              "destination": "ORD", "date": "2026-11-02", "departure_time": "09:15",
              "operated_by": "AcmeAir"}],
              "searched_at": "2026-10-20T08:50:00"})],
         CALL6,
         [ev("flight_id", "UA-8842", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-07: date in the past vs valid ------------------------------------
CASES += [
    case("NV-07a", "LP-07",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"})],
         FLIGHT_CALL,
         [ev("date", "2026-11-02", [ref("turn.1", "traveler", "user_current", match="2026-11-02")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-07b", "LP-07",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy."),
          turn(2, "Wait — that's yesterday's date I meant. Use 2026-11-02 anyway.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-19T08:50:00"})],
         FLIGHT_CALL,
         [ev("date", "2026-11-02", [ref("turn.1", "traveler", "user_current", match="2026-11-02")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-19T08:50:00")])]),
]

# --- LP-08: duplicate existing booking ------------------------------------
CASES += [
    case("NV-08a", "LP-08",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t4", "list_bookings", {"bookings": []})],
         FLIGHT_CALL,
         [ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-08b", "LP-08",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t4", "list_bookings", {"bookings": [{"ref": "BK-991", "flight_id": "FL-2201",
              "traveler": "Dana Whitfield", "date": "2026-11-02"}]})],
         FLIGHT_CALL,
         [ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-09: minor traveler -------------------------------------------------
CALL9 = {"tool": "book_flight", "arguments": dict(
    FLIGHT_CALL["arguments"], traveler_name="Theo Whitfield", passenger_dob="2012-07-30")}
CASES += [
    case("NV-09a", "LP-09",
         [turn(1, "Book my son Theo Whitfield SFO to JFK on 2026-11-02, 09:15, economy — I'll be on the same flight, already booked.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Theo Whitfield", "dob": "2012-07-30"})],
         CALL9,
         [ev("traveler_name", "Theo Whitfield", [ref("turn.1", "traveler", "user_current", match="Theo Whitfield")]),
          ev("passenger_dob", "2012-07-30", [ref("tool.t2.output.dob", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])],
         ctx={**CTX, "flying_person": "Theo Whitfield"}),
    case("NV-09b", "LP-09",
         [turn(1, "Book my son Theo Whitfield SFO to JFK on 2026-11-02, 09:15, economy. He's flying alone.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15",
              "unaccompanied_minor_allowed": False}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Theo Whitfield", "dob": "2012-07-30"})],
         CALL9,
         [ev("traveler_name", "Theo Whitfield", [ref("turn.1", "traveler", "user_current", match="Theo Whitfield")]),
          ev("passenger_dob", "2012-07-30", [ref("tool.t2.output.dob", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])],
         ctx={**CTX, "flying_person": "Theo Whitfield"}),
]

# --- LP-10: allergy (safety) vs preference --------------------------------
CALL10 = {"tool": "book_flight", "arguments": dict(FLIGHT_CALL["arguments"], meal="standard")}
CASES += [
    case("NV-10a", "LP-10",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy. Standard meal is fine.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Dana Whitfield", "dob": "1988-03-11"})],
         CALL10,
         [ev("meal", "standard", [ref("turn.1", "traveler", "user_current", match="Standard meal")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-10b", "LP-10",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Dana Whitfield", "dob": "1988-03-11",
              "allergies": "severe peanut allergy"})],
         CALL10,
         [ev("meal", "standard", [], transform="schema_default"),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-11: seat preference optional arg ----------------------------------
CALL11 = {"tool": "book_flight", "arguments": dict(FLIGHT_CALL["arguments"], seat="aisle")}
CASES += [
    case("NV-11a", "LP-11",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy — aisle seat please.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"})],
         CALL11,
         [ev("seat", "aisle", [ref("turn.1", "traveler", "user_current", match="aisle")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-11b", "LP-11",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"})],
         CALL11,
         [ev("seat", "aisle", [ref("tool.t2.output.seat_pref", "traveler", "profile")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-12: ambiguous group size ------------------------------------------
CALL12 = {"tool": "book_flight", "arguments": dict(FLIGHT_CALL["arguments"], num_passengers=2)}
CASES += [
    case("NV-12a", "LP-12",
         [turn(1, "Book two seats, SFO to JFK on 2026-11-02, 09:15, economy — for me and Rosa Delgado.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"})],
         CALL12,
         [ev("num_passengers", 2, [ref("turn.1", "unknown", "user_current", match="two seats")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-12b", "LP-12",
         [turn(1, "Book us SFO to JFK on 2026-11-02, 09:15, economy — the whole team is coming.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"})],
         CALL12,
         [ev("num_passengers", 2, [ref("turn.1", "unknown", "user_current", match="us")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-13: price cap ------------------------------------------------------
CASES += [
    case("NV-13a", "LP-13",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy — keep it under $500.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15",
              "price_usd": 420}], "searched_at": "2026-10-20T08:50:00"})],
         FLIGHT_CALL,
         [ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-13b", "LP-13",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy — keep it under $500.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15",
              "price_usd": 640}], "searched_at": "2026-10-20T08:50:00"})],
         FLIGHT_CALL,
         [ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-14: loyalty number, unauthorized profile ---------------------------
CALL14 = {"tool": "book_flight", "arguments": dict(FLIGHT_CALL["arguments"], loyalty_no="QF-55210")}
CTX14 = dict(CTX, profile_authorized=False)
CASES += [
    case("NV-14a", "LP-14",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy — loyalty number QF-55210.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"})],
         CALL14,
         [ev("loyalty_no", "QF-55210", [ref("turn.1", "traveler", "user_current", match="QF-55210")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])],
         ctx=CTX14),
    case("NV-14b", "LP-14",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"})],
         CALL14,
         [ev("loyalty_no", "QF-55210", [ref("tool.t2.output.loyalty_no", "traveler", "profile")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])],
         ctx=CTX14),
]

# --- LP-15: vague time "after 6pm" -----------------------------------------
CALL15 = {"tool": "book_flight", "arguments": dict(
    FLIGHT_CALL["arguments"], departure_time="18:30")}
CASES += [
    case("NV-15a", "LP-15",
         [turn(1, "Book me SFO to JFK on 2026-11-02, after 6pm, economy.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "18:30"}],
              "searched_at": "2026-10-20T08:50:00"})],
         CALL15,
         [ev("departure_time", "18:30", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-15b", "LP-15",
         [turn(1, "Book me SFO to JFK on 2026-11-02, after 6pm, economy.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [
              {"flight_id": "FL-2201", "origin": "SFO", "destination": "JFK",
               "date": "2026-11-02", "departure_time": "18:30"},
              {"flight_id": "FL-2214", "origin": "SFO", "destination": "JFK",
               "date": "2026-11-02", "departure_time": "20:45"}],
              "searched_at": "2026-10-20T08:50:00"})],
         CALL15,
         [ev("departure_time", "18:30", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-16: name change; profile has old name ------------------------------
CALL16 = {"tool": "book_flight", "arguments": dict(
    FLIGHT_CALL["arguments"], traveler_name="Dana Reyes")}
CASES += [
    case("NV-16a", "LP-16",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy — ticket under my new name Dana Reyes, it changed last month.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Dana Whitfield", "dob": "1988-03-11"})],
         CALL16,
         [ev("traveler_name", "Dana Reyes", [ref("turn.1", "traveler", "user_current", match="Dana Reyes")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-16b", "LP-16",
         [turn(1, "Book me SFO to JFK on 2026-11-02, 09:15, economy.")],
         FLIGHT_SCHEMA,
         [tool("t1", "search_flights", {"flights": [{"flight_id": "FL-2201", "origin": "SFO",
              "destination": "JFK", "date": "2026-11-02", "departure_time": "09:15"}],
              "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Dana Whitfield", "dob": "1988-03-11"})],
         CALL16,
         [ev("traveler_name", "Dana Reyes", [ref("tool.t2.output.full_name", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("flight_id", "FL-2201", [ref("tool.t1.output.flights", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-17: hotel, checkout before checkin ---------------------------------
HOTEL_CALL = {"tool": "reserve_hotel", "arguments": {
    "guest_name": "Dana Whitfield", "hotel_id": "HT-31",
    "checkin_date": "2026-11-02", "checkout_date": "2026-11-01",
    "room_type": "standard", "nightly_rate": 210}}
CASES += [
    case("NV-17a", "LP-17",
         [turn(1, "Reserve a standard room at the Paramount for 2026-11-02, checking out 2026-11-01… wait, I mean checking out 2026-11-04.")],
         HOTEL_SCHEMA,
         [tool("t1", "search_hotels", {"hotels": [{"hotel_id": "HT-31", "name": "Paramount",
              "nightly_rate": 210}], "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Dana Whitfield"})],
         HOTEL_CALL,
         [ev("guest_name", "Dana Whitfield", [ref("tool.t2.output.full_name", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("checkin_date", "2026-11-02", [ref("turn.1", "traveler", "user_current", match="2026-11-02")]),
          ev("checkout_date", "2026-11-01", [ref("turn.1", "traveler", "user_current", match="2026-11-01")]),
          ev("hotel_id", "HT-31", [ref("tool.t1.output.hotels", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-17b", "LP-17",
         [turn(1, "Reserve a standard room at the Paramount for 2026-11-02, checking out 2026-11-01.")],
         HOTEL_SCHEMA,
         [tool("t1", "search_hotels", {"hotels": [{"hotel_id": "HT-31", "name": "Paramount",
              "nightly_rate": 210}], "searched_at": "2026-10-20T08:50:00"}),
          tool("t2", "get_profile", {"full_name": "Dana Whitfield"})],
         HOTEL_CALL,
         [ev("guest_name", "Dana Whitfield", [ref("tool.t2.output.full_name", "traveler", "profile", "2026-10-20T08:50:00")]),
          ev("checkin_date", "2026-11-02", [ref("turn.1", "traveler", "user_current", match="2026-11-02")]),
          ev("checkout_date", "2026-11-01", [ref("turn.1", "traveler", "user_current", match="2026-11-01")]),
          ev("hotel_id", "HT-31", [ref("tool.t1.output.hotels", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-18: car rental pickup ambiguity ------------------------------------
CAR_CALL = {"tool": "rent_car", "arguments": {
    "driver_name": "Dana Whitfield", "pickup_location": "JFK Airport",
    "pickup_date": "2026-11-02", "dropoff_date": "2026-11-05",
    "car_class": "sedan"}}
CASES += [
    case("NV-18a", "LP-18",
         [turn(1, "Rent a sedan at JFK Airport, picking up 2026-11-02 and returning 2026-11-05.")],
         CAR_SCHEMA,
         [tool("t2", "get_profile", {"full_name": "Dana Whitfield"})],
         CAR_CALL,
         [ev("pickup_location", "JFK Airport", [ref("turn.1", "traveler", "user_current", match="JFK Airport")]),
          ev("car_class", "sedan", [ref("turn.1", "traveler", "user_current", match="sedan")])]),
    case("NV-18b", "LP-18",
         [turn(1, "Rent a sedan when I land in New York, 2026-11-02 to 2026-11-05.")],
         CAR_SCHEMA,
         [tool("t2", "get_profile", {"full_name": "Dana Whitfield"}),
          tool("t5", "list_locations", {"locations": ["JFK Airport", "LaGuardia Airport",
              "Manhattan Downtown"]})],
         CAR_CALL,
         [ev("pickup_location", "JFK Airport", [ref("tool.t5.output.locations", "unknown", "tool_result", "2026-10-20T08:50:00")]),
          ev("car_class", "sedan", [ref("turn.1", "traveler", "user_current", match="sedan")])]),
]

# --- LP-19: event ticket quantity ------------------------------------------
TICKET_CALL = {"tool": "buy_event_ticket", "arguments": {
    "buyer_name": "Dana Whitfield", "event_id": "EV-77",
    "quantity": 4, "section": "lower"}}
CASES += [
    case("NV-19a", "LP-19",
         [turn(1, "Get 4 tickets for EV-77, lower section.")],
         TICKET_SCHEMA,
         [tool("t1", "get_event", {"event_id": "EV-77", "title": "Symphony Gala",
              "sections_available": ["floor", "lower"], "max_per_order": 6})],
         TICKET_CALL,
         [ev("quantity", 4, [ref("turn.1", "unknown", "user_current", match="4 tickets")]),
          ev("section", "lower", [ref("turn.1", "unknown", "user_current", match="lower")]),
          ev("event_id", "EV-77", [ref("tool.t1.output.event_id", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
    case("NV-19b", "LP-19",
         [turn(1, "Get 4 tickets for EV-77, lower section.")],
         TICKET_SCHEMA,
         [tool("t1", "get_event", {"event_id": "EV-77", "title": "Symphony Gala",
              "sections_available": ["floor", "lower"], "max_per_order": 2})],
         TICKET_CALL,
         [ev("quantity", 4, [ref("turn.1", "unknown", "user_current", match="4 tickets")]),
          ev("section", "lower", [ref("turn.1", "unknown", "user_current", match="lower")]),
          ev("event_id", "EV-77", [ref("tool.t1.output.event_id", "unknown", "tool_result", "2026-10-20T08:50:00")])]),
]

# --- LP-20: change_flight; two bookings ------------------------------------
CHANGE_CALL = {"tool": "change_flight", "arguments": {
    "booking_ref": "BK-991", "new_date": "2026-11-09", "new_departure_time": "07:00"}}
CASES += [
    case("NV-20a", "LP-20",
         [turn(1, "Move my JFK trip, booking BK-991, to 2026-11-09 at 07:00.")],
         CHANGE_SCHEMA,
         [tool("t4", "list_bookings", {"bookings": [{"ref": "BK-991", "route": "SFO-JFK",
              "date": "2026-11-02"}]})],
         CHANGE_CALL,
         [ev("booking_ref", "BK-991", [ref("turn.1", "traveler", "user_current", match="BK-991")]),
          ev("new_date", "2026-11-09", [ref("turn.1", "traveler", "user_current", match="2026-11-09")])]),
    case("NV-20b", "LP-20",
         [turn(1, "Move my JFK trip to 2026-11-09 at 07:00.")],
         CHANGE_SCHEMA,
         [tool("t4", "list_bookings", {"bookings": [
              {"ref": "BK-991", "route": "SFO-JFK", "date": "2026-11-02"},
              {"ref": "BK-987", "route": "JFK-BOS", "date": "2026-11-03"}]})],
         CHANGE_CALL,
         [ev("booking_ref", "BK-991", [ref("tool.t4.output.bookings", "unknown", "tool_result", "2026-10-20T08:50:00")]),
          ev("new_date", "2026-11-09", [ref("turn.1", "traveler", "user_current", match="2026-11-09")])]),
]


def main() -> None:
    doc = {"shared_tool_schema": FLIGHT_SCHEMA,
           "note": ("Unlabeled set for human labeling. expected_* fields are "
                    "empty pending review. Pair members share identical "
                    "proposed_tool_call; only evidence differs."),
           "cases": CASES}
    OUT.write_text(json.dumps(doc, indent=2))
    pairs = {c["pair_id"] for c in CASES}
    print(f"Wrote {OUT}: {len(CASES)} cases, {len(pairs)} pairs")


if __name__ == "__main__":
    main()
