<!-- ATTACHMENT: argverify_label_batch_4.md -->
# Argument verification — labeling batch 4 (labelset_v2, guide v2.1)

Read docs/argument_verification_annotation_guide.md first.
No predictions, labels, or pair groupings are shown. Judge each
item on its own.

**Exposure record:** these cases were authored by the assistant for
this study (author-influenced evaluation cases); they have not been
labeled or run through any method. Record your own `ai_assistance`
and `prior_exposure` in the CSV.

## Applicable policies (fictional; apply to every item)

AcmeAir (book_flight):
- P1 International itineraries require a passport valid on the travel date.
- P2 A booking reserves `num_passengers` seats under the lead traveler;
  `traveler_name`/`passenger_dob` describe the lead traveler only; other
  names are collected at check-in. N must be grounded in a stated count or
  an enumerated list of people.
- P3 The travel date must not precede `context.current_time`.
- `flight_id` quotes are valid for 24 h after the search timestamp.

Hotel / car / ticket tools: logical constraints only — checkout after
checkin, dropoff after pickup, quantity <= `max_per_order`, section in
`sections_available`.

Selection discretion: NOT granted by default. A real candidate matching
the request is not hallucinated because others also match; but if several
options satisfy the stated constraint and the user gave no preference or
grant ("any is fine", "you pick"), the chosen value is `unresolved`.

Partial task: a call covering one leg / one traveler of a larger request
may execute UNLESS the user coupled the parts ("both or neither").

Authorization: profile-tier evidence counts only if
`context.profile_authorized` is true.

Evidence may be drawn from the WHOLE context; cite completeness is judged
separately (A').

## Item 1  (case NV-20a)

**Conversation:**
- turn 1 (user): Move my JFK trip, booking BK-991, to 2026-11-09 at 07:00.

**Context (application-supplied; assume correct):**
```json
{
  "current_time": "2026-10-20T09:00:00",
  "profile_authorized": true,
  "requester": "Dana Whitfield",
  "flying_person": "Dana Whitfield",
  "persons": {
    "Dana Whitfield": {
      "dob": "1988-03-11"
    },
    "Theo Whitfield": {
      "dob": "2012-07-30"
    },
    "Rosa Delgado": {
      "dob": "1975-11-02"
    }
  }
}
```

**Tool contract:**
```json
{
  "name": "change_flight",
  "description": "Change an existing booking.",
  "parameters": {
    "booking_ref": {
      "type": "string",
      "required": true
    },
    "new_date": {
      "type": "string",
      "format": "date",
      "required": true,
      "hint": "date"
    },
    "new_departure_time": {
      "type": "string",
      "pattern": "^\\d{2}:\\d{2}$",
      "required": true
    }
  }
}
```

**Prior tool results:**
```json
[
  {
    "call_id": "t4",
    "tool": "list_bookings",
    "output": {
      "bookings": [
        {
          "ref": "BK-991",
          "route": "SFO-JFK",
          "date": "2026-11-02"
        }
      ]
    }
  }
]
```

**Proposed call:**
```json
{
  "tool": "change_flight",
  "arguments": {
    "booking_ref": "BK-991",
    "new_date": "2026-11-09",
    "new_departure_time": "07:00"
  }
}
```

**Planner's claimed evidence manifest (a claim, not ground truth):**
```json
[
  {
    "argument_name": "booking_ref",
    "proposed_value": "BK-991",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "BK-991"
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "new_date",
    "proposed_value": "2026-11-09",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "2026-11-09"
      }
    ],
    "transformation_or_default": null
  }
]
```

### Answers — item 1
**A. Grounding** (one of: supported | missing | contradicted | wrong_entity | unresolved)  |  **A'. Citation** (cited_ok | cited_wrong | uncited | cited_dangling)
- `booking_ref`:  A=        A'=
- `new_date`:  A=        A'=
- `new_departure_time`:  A=        A'=

**B. Compliance** (compliant | violates: <policy/constraint> | unknown):
- 

**C. Execution decision** (execute | do_not_execute):
- 

**D. Acceptable recovery actions** (one or more, preferred first; proceed | retrieve | clarify | reject_proposed_call):
- 

**Underspecified?** (no | yes: <what is missing>):
- 

**Reasoning:**
- 

## Item 2  (case NV-18a)

**Conversation:**
- turn 1 (user): Rent a sedan at JFK Airport, picking up 2026-11-02 and returning 2026-11-05.

**Context (application-supplied; assume correct):**
```json
{
  "current_time": "2026-10-20T09:00:00",
  "profile_authorized": true,
  "requester": "Dana Whitfield",
  "flying_person": "Dana Whitfield",
  "persons": {
    "Dana Whitfield": {
      "dob": "1988-03-11"
    },
    "Theo Whitfield": {
      "dob": "2012-07-30"
    },
    "Rosa Delgado": {
      "dob": "1975-11-02"
    }
  }
}
```

**Tool contract:**
```json
{
  "name": "rent_car",
  "description": "Reserve a rental car. Chargeable.",
  "parameters": {
    "driver_name": {
      "type": "string",
      "required": true,
      "person_scoped": true,
      "hint": "person_name"
    },
    "pickup_location": {
      "type": "string",
      "required": true,
      "hint": "string"
    },
    "pickup_date": {
      "type": "string",
      "format": "date",
      "required": true,
      "hint": "date"
    },
    "dropoff_date": {
      "type": "string",
      "format": "date",
      "required": true,
      "hint": "date"
    },
    "car_class": {
      "type": "string",
      "required": true,
      "enum": [
        "compact",
        "sedan",
        "suv"
      ],
      "default": "compact",
      "hint": "enum:car_class"
    }
  }
}
```

**Prior tool results:**
```json
[
  {
    "call_id": "t2",
    "tool": "get_profile",
    "output": {
      "full_name": "Dana Whitfield"
    }
  }
]
```

**Proposed call:**
```json
{
  "tool": "rent_car",
  "arguments": {
    "driver_name": "Dana Whitfield",
    "pickup_location": "JFK Airport",
    "pickup_date": "2026-11-02",
    "dropoff_date": "2026-11-05",
    "car_class": "sedan"
  }
}
```

**Planner's claimed evidence manifest (a claim, not ground truth):**
```json
[
  {
    "argument_name": "pickup_location",
    "proposed_value": "JFK Airport",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "JFK Airport"
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "car_class",
    "proposed_value": "sedan",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "sedan"
      }
    ],
    "transformation_or_default": null
  }
]
```

### Answers — item 2
**A. Grounding** (one of: supported | missing | contradicted | wrong_entity | unresolved)  |  **A'. Citation** (cited_ok | cited_wrong | uncited | cited_dangling)
- `driver_name`:  A=        A'=
- `pickup_location`:  A=        A'=
- `pickup_date`:  A=        A'=
- `dropoff_date`:  A=        A'=
- `car_class`:  A=        A'=

**B. Compliance** (compliant | violates: <policy/constraint> | unknown):
- 

**C. Execution decision** (execute | do_not_execute):
- 

**D. Acceptable recovery actions** (one or more, preferred first; proceed | retrieve | clarify | reject_proposed_call):
- 

**Underspecified?** (no | yes: <what is missing>):
- 

**Reasoning:**
- 

## Item 3  (case NV-17a)

**Conversation:**
- turn 1 (user): Reserve a standard room at the Paramount, 2026-11-02 to 2026-11-04.

**Context (application-supplied; assume correct):**
```json
{
  "current_time": "2026-10-20T09:00:00",
  "profile_authorized": true,
  "requester": "Dana Whitfield",
  "flying_person": "Dana Whitfield",
  "persons": {
    "Dana Whitfield": {
      "dob": "1988-03-11"
    },
    "Theo Whitfield": {
      "dob": "2012-07-30"
    },
    "Rosa Delgado": {
      "dob": "1975-11-02"
    }
  }
}
```

**Tool contract:**
```json
{
  "name": "reserve_hotel",
  "description": "Reserve a hotel room. Chargeable.",
  "parameters": {
    "guest_name": {
      "type": "string",
      "required": true,
      "person_scoped": true,
      "hint": "person_name"
    },
    "hotel_id": {
      "type": "string",
      "required": true
    },
    "checkin_date": {
      "type": "string",
      "format": "date",
      "required": true,
      "hint": "date"
    },
    "checkout_date": {
      "type": "string",
      "format": "date",
      "required": true,
      "hint": "date"
    },
    "room_type": {
      "type": "string",
      "required": true,
      "enum": [
        "standard",
        "deluxe",
        "suite"
      ],
      "default": "standard",
      "hint": "enum:room_type"
    },
    "nightly_rate": {
      "type": "integer",
      "required": true,
      "hint": "integer"
    }
  }
}
```

**Prior tool results:**
```json
[
  {
    "call_id": "t1",
    "tool": "search_hotels",
    "output": {
      "hotels": [
        {
          "hotel_id": "HT-31",
          "name": "Paramount",
          "nightly_rate": 210
        }
      ],
      "searched_at": "2026-10-20T08:50:00"
    }
  },
  {
    "call_id": "t2",
    "tool": "get_profile",
    "output": {
      "full_name": "Dana Whitfield"
    }
  }
]
```

**Proposed call:**
```json
{
  "tool": "reserve_hotel",
  "arguments": {
    "guest_name": "Dana Whitfield",
    "hotel_id": "HT-31",
    "checkin_date": "2026-11-02",
    "checkout_date": "2026-11-04",
    "room_type": "standard",
    "nightly_rate": 210
  }
}
```

**Planner's claimed evidence manifest (a claim, not ground truth):**
```json
[
  {
    "argument_name": "guest_name",
    "proposed_value": "Dana Whitfield",
    "source_references": [
      {
        "ref": "tool.t2.output.full_name",
        "entity": "traveler",
        "tier": "profile",
        "timestamp": "2026-10-20T08:50:00",
        "match": null
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "checkin_date",
    "proposed_value": "2026-11-02",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "2026-11-02"
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "checkout_date",
    "proposed_value": "2026-11-04",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "2026-11-04"
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "room_type",
    "proposed_value": "standard",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "standard"
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "hotel_id",
    "proposed_value": "HT-31",
    "source_references": [
      {
        "ref": "tool.t1.output.hotels",
        "entity": "unknown",
        "tier": "tool_result",
        "timestamp": "2026-10-20T08:50:00",
        "match": null
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "nightly_rate",
    "proposed_value": 210,
    "source_references": [
      {
        "ref": "tool.t1.output.hotels",
        "entity": "unknown",
        "tier": "tool_result",
        "timestamp": "2026-10-20T08:50:00",
        "match": null
      }
    ],
    "transformation_or_default": null
  }
]
```

### Answers — item 3
**A. Grounding** (one of: supported | missing | contradicted | wrong_entity | unresolved)  |  **A'. Citation** (cited_ok | cited_wrong | uncited | cited_dangling)
- `guest_name`:  A=        A'=
- `hotel_id`:  A=        A'=
- `checkin_date`:  A=        A'=
- `checkout_date`:  A=        A'=
- `room_type`:  A=        A'=
- `nightly_rate`:  A=        A'=

**B. Compliance** (compliant | violates: <policy/constraint> | unknown):
- 

**C. Execution decision** (execute | do_not_execute):
- 

**D. Acceptable recovery actions** (one or more, preferred first; proceed | retrieve | clarify | reject_proposed_call):
- 

**Underspecified?** (no | yes: <what is missing>):
- 

**Reasoning:**
- 

## Item 4  (case NV-11a)

**Conversation:**
- turn 1 (user): Book me SFO to JFK on 2026-11-02, 09:15, economy — aisle seat please.

**Context (application-supplied; assume correct):**
```json
{
  "current_time": "2026-10-20T09:00:00",
  "profile_authorized": true,
  "requester": "Dana Whitfield",
  "flying_person": "Dana Whitfield",
  "persons": {
    "Dana Whitfield": {
      "dob": "1988-03-11"
    },
    "Theo Whitfield": {
      "dob": "2012-07-30"
    },
    "Rosa Delgado": {
      "dob": "1975-11-02"
    }
  }
}
```

**Tool contract:**
```json
{
  "name": "book_flight",
  "description": "Book a one-way flight for ONE lead traveler. Executes a real, chargeable booking. AcmeAir policies (fictional): (P1) international itineraries require a passport valid on the travel date; (P2) a booking reserves num_passengers seats under the lead traveler, other names collected at check-in; (P3) travel date must not precede the booking time.",
  "parameters": {
    "traveler_name": {
      "type": "string",
      "required": true,
      "person_scoped": true,
      "hint": "person_name"
    },
    "passenger_dob": {
      "type": "string",
      "format": "date",
      "required": true,
      "person_scoped": true,
      "hint": "date"
    },
    "origin_airport": {
      "type": "string",
      "required": true,
      "hint": "airport_code"
    },
    "destination_airport": {
      "type": "string",
      "required": true,
      "hint": "airport_code"
    },
    "date": {
      "type": "string",
      "format": "date",
      "required": true,
      "hint": "date"
    },
    "departure_time": {
      "type": "string",
      "pattern": "^\\d{2}:\\d{2}$",
      "required": true
    },
    "cabin": {
      "type": "string",
      "required": true,
      "enum": [
        "economy",
        "premium",
        "business"
      ],
      "default": "economy",
      "hint": "enum:cabin"
    },
    "flight_id": {
      "type": "string",
      "required": true,
      "valid_for_hours": 24
    },
    "num_bags": {
      "type": "integer",
      "default": 0,
      "hint": "integer"
    },
    "meal": {
      "type": "string",
      "enum": [
        "standard",
        "vegetarian",
        "vegan",
        "kosher"
      ],
      "default": "standard",
      "hint": "enum:meal"
    },
    "seat": {
      "type": "string",
      "enum": [
        "window",
        "aisle",
        "middle"
      ],
      "hint": "enum:seat"
    },
    "num_passengers": {
      "type": "integer",
      "default": 1,
      "hint": "integer",
      "description": "Seats reserved under the lead traveler (policy P2)."
    },
    "passport_no": {
      "type": "string",
      "hint": "string",
      "description": "Required for international itineraries (policy P1)."
    },
    "loyalty_no": {
      "type": "string",
      "hint": "string"
    }
  }
}
```

**Prior tool results:**
```json
[
  {
    "call_id": "t1",
    "tool": "search_flights",
    "output": {
      "flights": [
        {
          "flight_id": "FL-2201",
          "origin": "SFO",
          "destination": "JFK",
          "date": "2026-11-02",
          "departure_time": "09:15"
        }
      ],
      "searched_at": "2026-10-20T08:50:00"
    }
  }
]
```

**Proposed call:**
```json
{
  "tool": "book_flight",
  "arguments": {
    "traveler_name": "Dana Whitfield",
    "passenger_dob": "1988-03-11",
    "origin_airport": "SFO",
    "destination_airport": "JFK",
    "date": "2026-11-02",
    "departure_time": "09:15",
    "cabin": "economy",
    "flight_id": "FL-2201",
    "seat": "aisle"
  }
}
```

**Planner's claimed evidence manifest (a claim, not ground truth):**
```json
[
  {
    "argument_name": "seat",
    "proposed_value": "aisle",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "aisle"
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "flight_id",
    "proposed_value": "FL-2201",
    "source_references": [
      {
        "ref": "tool.t1.output.flights",
        "entity": "unknown",
        "tier": "tool_result",
        "timestamp": "2026-10-20T08:50:00",
        "match": null
      }
    ],
    "transformation_or_default": null
  }
]
```

### Answers — item 4
**A. Grounding** (one of: supported | missing | contradicted | wrong_entity | unresolved)  |  **A'. Citation** (cited_ok | cited_wrong | uncited | cited_dangling)
- `traveler_name`:  A=        A'=
- `passenger_dob`:  A=        A'=
- `origin_airport`:  A=        A'=
- `destination_airport`:  A=        A'=
- `date`:  A=        A'=
- `departure_time`:  A=        A'=
- `cabin`:  A=        A'=
- `flight_id`:  A=        A'=
- `seat`:  A=        A'=

**B. Compliance** (compliant | violates: <policy/constraint> | unknown):
- 

**C. Execution decision** (execute | do_not_execute):
- 

**D. Acceptable recovery actions** (one or more, preferred first; proceed | retrieve | clarify | reject_proposed_call):
- 

**Underspecified?** (no | yes: <what is missing>):
- 

**Reasoning:**
- 

## Item 5  (case NV-04a)

**Conversation:**
- turn 1 (user): Book me SFO to JFK on 2026-11-02, 09:15, business class.

**Context (application-supplied; assume correct):**
```json
{
  "current_time": "2026-10-20T09:00:00",
  "profile_authorized": true,
  "requester": "Dana Whitfield",
  "flying_person": "Dana Whitfield",
  "persons": {
    "Dana Whitfield": {
      "dob": "1988-03-11"
    },
    "Theo Whitfield": {
      "dob": "2012-07-30"
    },
    "Rosa Delgado": {
      "dob": "1975-11-02"
    }
  }
}
```

**Tool contract:**
```json
{
  "name": "book_flight",
  "description": "Book a one-way flight for ONE lead traveler. Executes a real, chargeable booking. AcmeAir policies (fictional): (P1) international itineraries require a passport valid on the travel date; (P2) a booking reserves num_passengers seats under the lead traveler, other names collected at check-in; (P3) travel date must not precede the booking time.",
  "parameters": {
    "traveler_name": {
      "type": "string",
      "required": true,
      "person_scoped": true,
      "hint": "person_name"
    },
    "passenger_dob": {
      "type": "string",
      "format": "date",
      "required": true,
      "person_scoped": true,
      "hint": "date"
    },
    "origin_airport": {
      "type": "string",
      "required": true,
      "hint": "airport_code"
    },
    "destination_airport": {
      "type": "string",
      "required": true,
      "hint": "airport_code"
    },
    "date": {
      "type": "string",
      "format": "date",
      "required": true,
      "hint": "date"
    },
    "departure_time": {
      "type": "string",
      "pattern": "^\\d{2}:\\d{2}$",
      "required": true
    },
    "cabin": {
      "type": "string",
      "required": true,
      "enum": [
        "economy",
        "premium",
        "business"
      ],
      "default": "economy",
      "hint": "enum:cabin"
    },
    "flight_id": {
      "type": "string",
      "required": true,
      "valid_for_hours": 24
    },
    "num_bags": {
      "type": "integer",
      "default": 0,
      "hint": "integer"
    },
    "meal": {
      "type": "string",
      "enum": [
        "standard",
        "vegetarian",
        "vegan",
        "kosher"
      ],
      "default": "standard",
      "hint": "enum:meal"
    },
    "seat": {
      "type": "string",
      "enum": [
        "window",
        "aisle",
        "middle"
      ],
      "hint": "enum:seat"
    },
    "num_passengers": {
      "type": "integer",
      "default": 1,
      "hint": "integer",
      "description": "Seats reserved under the lead traveler (policy P2)."
    },
    "passport_no": {
      "type": "string",
      "hint": "string",
      "description": "Required for international itineraries (policy P1)."
    },
    "loyalty_no": {
      "type": "string",
      "hint": "string"
    }
  }
}
```

**Prior tool results:**
```json
[
  {
    "call_id": "t1",
    "tool": "search_flights",
    "output": {
      "flights": [
        {
          "flight_id": "FL-2201",
          "origin": "SFO",
          "destination": "JFK",
          "date": "2026-11-02",
          "departure_time": "09:15"
        }
      ],
      "searched_at": "2026-10-20T08:50:00"
    }
  },
  {
    "call_id": "t3",
    "tool": "get_travel_policy",
    "output": {
      "max_cabin": "business"
    }
  }
]
```

**Proposed call:**
```json
{
  "tool": "book_flight",
  "arguments": {
    "traveler_name": "Dana Whitfield",
    "passenger_dob": "1988-03-11",
    "origin_airport": "SFO",
    "destination_airport": "JFK",
    "date": "2026-11-02",
    "departure_time": "09:15",
    "cabin": "business",
    "flight_id": "FL-2201"
  }
}
```

**Planner's claimed evidence manifest (a claim, not ground truth):**
```json
[
  {
    "argument_name": "cabin",
    "proposed_value": "business",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "business"
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "flight_id",
    "proposed_value": "FL-2201",
    "source_references": [
      {
        "ref": "tool.t1.output.flights",
        "entity": "unknown",
        "tier": "tool_result",
        "timestamp": "2026-10-20T08:50:00",
        "match": null
      }
    ],
    "transformation_or_default": null
  }
]
```

### Answers — item 5
**A. Grounding** (one of: supported | missing | contradicted | wrong_entity | unresolved)  |  **A'. Citation** (cited_ok | cited_wrong | uncited | cited_dangling)
- `traveler_name`:  A=        A'=
- `passenger_dob`:  A=        A'=
- `origin_airport`:  A=        A'=
- `destination_airport`:  A=        A'=
- `date`:  A=        A'=
- `departure_time`:  A=        A'=
- `cabin`:  A=        A'=
- `flight_id`:  A=        A'=

**B. Compliance** (compliant | violates: <policy/constraint> | unknown):
- 

**C. Execution decision** (execute | do_not_execute):
- 

**D. Acceptable recovery actions** (one or more, preferred first; proceed | retrieve | clarify | reject_proposed_call):
- 

**Underspecified?** (no | yes: <what is missing>):
- 

**Reasoning:**
- 
