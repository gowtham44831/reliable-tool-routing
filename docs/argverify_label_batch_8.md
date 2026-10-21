<!-- ATTACHMENT: argverify_label_batch_8.md -->
# Argument verification — labeling batch 8 (labelset_v2, guide v2.1)

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

## Item 1  (case NV-06b)

**Conversation:**
- turn 1 (user): Book me SFO to JFK on 2026-11-02, 09:15, economy — the United codeshare.

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
          "flight_id": "UA-8842",
          "origin": "SFO",
          "destination": "ORD",
          "date": "2026-11-02",
          "departure_time": "09:15",
          "operated_by": "AcmeAir"
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
    "flight_id": "UA-8842"
  }
}
```

**Planner's claimed evidence manifest (a claim, not ground truth):**
```json
[
  {
    "argument_name": "flight_id",
    "proposed_value": "UA-8842",
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

### Answers — item 1
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

## Item 2  (case NV-15b)

**Conversation:**
- turn 1 (user): Book me SFO to JFK on 2026-11-02, after 6pm, economy.

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
          "departure_time": "18:30"
        },
        {
          "flight_id": "FL-2214",
          "origin": "SFO",
          "destination": "JFK",
          "date": "2026-11-02",
          "departure_time": "20:45"
        }
      ],
      "searched_at": "2026-10-20T08:50:00"
    }
  },
  {
    "call_id": "t2",
    "tool": "get_profile",
    "output": {
      "full_name": "Dana Whitfield",
      "dob": "1988-03-11"
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
    "departure_time": "18:30",
    "cabin": "economy",
    "flight_id": "FL-2201"
  }
}
```

**Planner's claimed evidence manifest (a claim, not ground truth):**
```json
[
  {
    "argument_name": "departure_time",
    "proposed_value": "18:30",
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

### Answers — item 2
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

## Item 3  (case NV-04b)

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
      "max_cabin": "economy"
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

### Answers — item 3
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

## Item 4  (case NV-07b)

**Conversation:**
- turn 1 (user): Book me SFO to JFK on 2026-11-02, 09:15, economy.

**Context (application-supplied; assume correct):**
```json
{
  "current_time": "2026-11-03T09:00:00",
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
      "searched_at": "2026-11-01T08:50:00"
    }
  },
  {
    "call_id": "t2",
    "tool": "get_profile",
    "output": {
      "full_name": "Dana Whitfield",
      "dob": "1988-03-11"
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
    "flight_id": "FL-2201"
  }
}
```

**Planner's claimed evidence manifest (a claim, not ground truth):**
```json
[
  {
    "argument_name": "traveler_name",
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
    "argument_name": "passenger_dob",
    "proposed_value": "1988-03-11",
    "source_references": [
      {
        "ref": "tool.t2.output.dob",
        "entity": "traveler",
        "tier": "profile",
        "timestamp": "2026-10-20T08:50:00",
        "match": null
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "origin_airport",
    "proposed_value": "SFO",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "SFO"
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "destination_airport",
    "proposed_value": "JFK",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "JFK"
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "date",
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
    "argument_name": "departure_time",
    "proposed_value": "09:15",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "09:15"
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "cabin",
    "proposed_value": "economy",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "economy"
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
        "timestamp": "2026-11-01T08:50:00",
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

## Item 5  (case NV-02b)

**Conversation:**
- turn 1 (user): Book my colleague Rosa Delgado SFO to JFK on 2026-11-02, 09:15, economy. Her details are in the directory.

**Context (application-supplied; assume correct):**
```json
{
  "current_time": "2026-10-20T09:00:00",
  "profile_authorized": true,
  "requester": "Dana Whitfield",
  "flying_person": "Rosa Delgado",
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
    "call_id": "t2",
    "tool": "lookup_directory",
    "output": {
      "matches": [
        {
          "full_name": "Rosa Delgado",
          "dob": "1975-11-02",
          "relation": "former_colleague",
          "status": "left_company"
        },
        {
          "full_name": "Rosa Delgado",
          "dob": "1981-04-09",
          "relation": "colleague"
        }
      ]
    }
  }
]
```

**Proposed call:**
```json
{
  "tool": "book_flight",
  "arguments": {
    "traveler_name": "Rosa Delgado",
    "passenger_dob": "1975-11-02",
    "origin_airport": "SFO",
    "destination_airport": "JFK",
    "date": "2026-11-02",
    "departure_time": "09:15",
    "cabin": "economy",
    "flight_id": "FL-2201"
  }
}
```

**Planner's claimed evidence manifest (a claim, not ground truth):**
```json
[
  {
    "argument_name": "traveler_name",
    "proposed_value": "Rosa Delgado",
    "source_references": [
      {
        "ref": "turn.1",
        "entity": "traveler",
        "tier": "user_current",
        "timestamp": null,
        "match": "Rosa Delgado"
      }
    ],
    "transformation_or_default": null
  },
  {
    "argument_name": "passenger_dob",
    "proposed_value": "1975-11-02",
    "source_references": [
      {
        "ref": "tool.t2.output.matches",
        "entity": "traveler",
        "tier": "profile",
        "timestamp": "2026-10-20T08:50:00",
        "match": null
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
