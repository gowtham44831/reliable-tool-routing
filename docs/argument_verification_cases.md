# Travel-booking verification cases (10 pairs, development set)

Within each pair the proposed `book_flight` call is **identical**; only the evidence changes. Labels are derived from the `label_rules` stated per case. Fictional people, mocked tools, no real credentials.

## P01: TB-01a vs TB-01b

Proposed call (identical in both): `{"traveler_name": "Maya Chen", "passenger_dob": "1990-03-12", "origin_airport": "SFO", "destination_airport": "JFK", "date": "2026-12-01", "departure_time": "14:00", "cabin": "economy", "flight_id": "FL-4471"}`

### TB-01a — expected action: `proceed`

- flying_person=Maya Chen, profile_authorized=True, now=2026-10-19T10:00:00
- **user t1:** I'm Maya Chen. Book me a flight SFO to JFK on 2026-12-01, the 14:00 departure, economy. You can use my saved profile for my details.
- **tool lookup_traveler_profile** (2026-10-19T09:58:00): `{"full_name": "Maya Chen", "dob": "1990-03-12", "home_airport": "SFO", "preferred_cabin": "business", "meal_preference": "standard"}`
- **tool search_flights** (2026-10-19T09:00:00): `{"flights": [{"flight_id": "FL-4471", "origin": "SFO", "destination": "JFK", "date": "2026-12-01", "departure_time": "14:00"}]}`

| argument | expected finding |
|---|---|
| (all) | supported |

**Rules:** (1) Every proposed value appears verbatim in a current-turn or fresh authorized source. (2) flight_id quote is 1h old, inside the 24h validity window.

**Why:** All arguments are backed by the current user turn or a fresh authorized profile/tool result; the flight quote is within its 24h window.

### TB-01b — expected action: `reject_proposed_call`

- flying_person=Priya Nair, profile_authorized=True, now=2026-10-19T10:00:00
- **user t1:** I'm Maya Chen. Please book a flight for my sister Priya Nair — SFO to JFK on 2026-12-01, the 14:00 departure, economy.
- **tool lookup_traveler_profile** (2026-10-19T09:58:00): `{"full_name": "Maya Chen", "dob": "1990-03-12", "home_airport": "SFO", "preferred_cabin": "business", "meal_preference": "standard"}`
- **tool search_flights** (2026-10-19T09:00:00): `{"flights": [{"flight_id": "FL-4471", "origin": "SFO", "destination": "JFK", "date": "2026-12-01", "departure_time": "14:00"}]}`

| argument | expected finding |
|---|---|
| traveler_name | **wrong_entity** |
| passenger_dob | **wrong_entity** |

**Rules:** (1) Person-scoped arguments must refer to flying_person (Priya Nair). Proposed traveler_name and passenger_dob come from the requester's profile, a different person → wrong_entity. (2) wrong_entity makes the call unsafe to execute → reject_proposed_call.

**Why:** The requester is Maya Chen but the person flying is her sister Priya Nair; the call carries the requester's name and DOB. The call must not execute — this does not abandon the booking task.

## P02: TB-02a vs TB-02b

Proposed call (identical in both): `{"traveler_name": "Theo Marsh", "passenger_dob": "1988-07-04", "origin_airport": "DEN", "destination_airport": "AUS", "date": "2026-11-03", "departure_time": "09:00", "cabin": "economy", "flight_id": "FL-0900"}`

### TB-02a — expected action: `proceed`

- flying_person=Theo Marsh, profile_authorized=True, now=2026-10-19T10:00:00
- **user t1:** I'm Theo Marsh — book me DEN to AUS on 2026-11-03, specifically the 09:00 flight, economy, my DOB 1988-07-04.
- **tool search_flights** (2026-10-19T09:30:00): `{"flights": [{"flight_id": "FL-0900", "origin": "DEN", "destination": "AUS", "date": "2026-11-03", "departure_time": "09:00"}]}`

| argument | expected finding |
|---|---|
| (all) | supported |

**Rules:** (1) departure_time 09:00 is stated explicitly in the current turn AND appears as the sole matching flight result.

**Why:** The user named the exact departure time and the search returned exactly that flight; the quote is fresh.

### TB-02b — expected action: `clarify`

- flying_person=Theo Marsh, profile_authorized=True, now=2026-10-19T10:00:00
- **user t1:** I'm Theo Marsh — book me DEN to AUS on 2026-11-03, a morning flight, economy, my DOB 1988-07-04.
- **tool search_flights** (2026-10-19T09:30:00): `{"flights": [{"flight_id": "FL-0730", "origin": "DEN", "destination": "AUS", "date": "2026-11-03", "departure_time": "07:30"}, {"flight_id": "FL-0900", "origin": "DEN", "destination": "AUS", "date": "2026-11-03", "departure_time": "09:00"}, {"flight_id": "FL-1115", "origin": "DEN", "destination": "AUS", "date": "2026-11-03", "departure_time": "11:15"}]}`

| argument | expected finding |
|---|---|
| departure_time | **unresolved** |
| flight_id | **unresolved** |

**Rules:** (1) 'A morning flight' is not a specific time; three distinct candidate times exist in the search result → unresolved. (2) Only the user can pick among the candidates → clarify.

**Why:** 09:00 was invented by the proposer: three morning departures (07:30, 09:00, 11:15) are equally consistent with the request, so the time and the flight_id that follows from it are unresolved. Ask which flight.

## P03: TB-03a vs TB-03b

Proposed call (identical in both): `{"traveler_name": "Rena Okafor", "passenger_dob": "1993-01-22", "origin_airport": "PDX", "destination_airport": "ORD", "date": "2026-12-05", "departure_time": "08:15", "cabin": "economy", "flight_id": "FL-3301"}`

### TB-03a — expected action: `proceed`

- flying_person=Rena Okafor, profile_authorized=True, now=2026-10-19T10:00:00
- **user t1:** I'm Rena Okafor. Book PDX to ORD on 2026-12-05 at 08:15, DOB 1993-01-22. I usually fly business, but economy is fine this time.
- **tool lookup_traveler_profile** (2026-10-19T09:50:00): `{"full_name": "Rena Okafor", "preferred_cabin": "business"}`
- **tool search_flights** (2026-10-19T09:55:00): `{"flights": [{"flight_id": "FL-3301", "origin": "PDX", "destination": "ORD", "date": "2026-12-05", "departure_time": "08:15"}]}`

| argument | expected finding |
|---|---|
| (all) | supported |

**Rules:** (1) Case precedence: an explicit current-turn instruction overrides a stored preference for the same argument. 'Economy is fine this time' is current → economy is supported even though the profile says business.

**Why:** The stored preference (business) conflicts with the current instruction (economy); the current instruction wins for this booking, so economy is supported.

### TB-03b — expected action: `reject_proposed_call`

- flying_person=Rena Okafor, profile_authorized=True, now=2026-10-19T10:00:00
- **user t1:** I'm Rena Okafor. Book PDX to ORD on 2026-12-05 at 08:15, DOB 1993-01-22. I usually fly economy but put me in business this time.
- **tool lookup_traveler_profile** (2026-10-19T09:50:00): `{"full_name": "Rena Okafor", "preferred_cabin": "economy"}`
- **tool search_flights** (2026-10-19T09:55:00): `{"flights": [{"flight_id": "FL-3301", "origin": "PDX", "destination": "ORD", "date": "2026-12-05", "departure_time": "08:15"}]}`

| argument | expected finding |
|---|---|
| cabin | **contradicted** |

**Rules:** (1) Case precedence: current-turn instruction overrides stored preference. Current turn says business; call proposes economy → contradicted. (2) contradicted argument → the call must not execute → reject_proposed_call (replan with business).

**Why:** The profile's economy default leaked into the call while the user explicitly asked for business on this trip. The proposed call must not execute.

## P04: TB-04a vs TB-04b

Proposed call (identical in both): `{"traveler_name": "Sam Delacroix", "passenger_dob": "1985-09-30", "origin_airport": "BOS", "destination_airport": "MIA", "date": "2026-11-20", "departure_time": "16:45", "cabin": "economy", "flight_id": "FL-2210", "meal": "vegetarian"}`

### TB-04a — expected action: `proceed`

- flying_person=Sam Delacroix, profile_authorized=True, now=2026-10-19T10:00:00
- **user t1:** I'm Sam Delacroix. Book BOS to MIA on 2026-11-20 at 16:45, economy, DOB 1985-09-30. Feel free to use my saved profile.
- **tool lookup_traveler_profile** (2026-10-19T09:40:00): `{"full_name": "Sam Delacroix", "meal_preference": "vegetarian"}`
- **tool search_flights** (2026-10-19T09:45:00): `{"flights": [{"flight_id": "FL-2210", "origin": "BOS", "destination": "MIA", "date": "2026-11-20", "departure_time": "16:45"}]}`

| argument | expected finding |
|---|---|
| (all) | supported |

**Rules:** (1) Optional args may differ from the documented default only with evidence; authorized profile meal_preference=vegetarian counts as evidence.

**Why:** The vegetarian meal is not a guess: the authorized profile explicitly records it.

### TB-04b — expected action: `reject_proposed_call`

- flying_person=Sam Delacroix, profile_authorized=True, now=2026-10-19T10:00:00
- **user t1:** I'm Sam Delacroix. Book BOS to MIA on 2026-11-20 at 16:45, economy, DOB 1985-09-30. Feel free to use my saved profile.
- **tool lookup_traveler_profile** (2026-10-19T09:40:00): `{"full_name": "Sam Delacroix"}`
- **tool search_flights** (2026-10-19T09:45:00): `{"flights": [{"flight_id": "FL-2210", "origin": "BOS", "destination": "MIA", "date": "2026-11-20", "departure_time": "16:45"}]}`

| argument | expected finding |
|---|---|
| meal | **missing** |

**Rules:** (1) Optional args may differ from the documented default only with evidence. The profile result contains no meal field → the proposed 'vegetarian' has no supporting source → missing. (2) An unsupported optional argument makes the call unsafe as proposed → reject_proposed_call (a corrected call can simply omit meal and take the default).

**Why:** The claim 'vegetarian' cites a profile field that does not exist in the actual result — the evidence pointer resolves to nothing. The documented default is 'standard'; the call must not execute with an invented value.

## P05: TB-05a vs TB-05b

Proposed call (identical in both): `{"traveler_name": "Ines Vidal", "origin_airport": "ATL", "destination_airport": "SEA", "date": "2026-12-12", "departure_time": "10:30", "cabin": "premium", "flight_id": "FL-6100"}`

### TB-05a — expected action: `retrieve`

- flying_person=Ines Vidal, profile_authorized=True, now=2026-10-19T10:00:00
- **user t1:** I'm Ines Vidal — book ATL to SEA on 2026-12-12 at 10:30, premium, and pull whatever details you need from my saved profile.
- **tool search_flights** (2026-10-19T09:20:00): `{"flights": [{"flight_id": "FL-6100", "origin": "ATL", "destination": "SEA", "date": "2026-12-12", "departure_time": "10:30"}]}`

| argument | expected finding |
|---|---|
| passenger_dob | **missing** |

**Rules:** (1) passenger_dob is required and absent → missing. The user authorized 'pull whatever details you need from my saved profile' → obtainable by an authorized lookup_traveler_profile call → retrieve. (2) tool.profile_lookup.* is a prospective reference: it names a source that could supply the value, not a result already returned.

**Why:** DOB is required and missing, but the user explicitly authorized the profile lookup that supplies it — retrieve, don't ask.

### TB-05b — expected action: `clarify`

- flying_person=Ines Vidal, profile_authorized=False, now=2026-10-19T10:00:00
- **user t1:** I'm Ines Vidal — book ATL to SEA on 2026-12-12 at 10:30, premium.
- **tool search_flights** (2026-10-19T09:20:00): `{"flights": [{"flight_id": "FL-6100", "origin": "ATL", "destination": "SEA", "date": "2026-12-12", "departure_time": "10:30"}]}`

| argument | expected finding |
|---|---|
| passenger_dob | **missing** |

**Rules:** (1) passenger_dob is required and absent → missing. No authorization for a profile lookup and no other source → the user must supply it → clarify.

**Why:** DOB is required, absent everywhere, and the system has no authorization to fetch it — ask the user.

## P06: TB-06a vs TB-06b

Proposed call (identical in both): `{"traveler_name": "Dev Rao", "passenger_dob": "1991-05-17", "origin_airport": "LAX", "destination_airport": "SPI", "date": "2026-11-08", "departure_time": "12:20", "cabin": "economy", "flight_id": "FL-7700"}`

### TB-06a — expected action: `proceed`

- flying_person=Dev Rao, profile_authorized=False, now=2026-10-19T10:00:00
- **user t1:** I'm Dev Rao, DOB 1991-05-17. Book LAX to Springfield, Illinois on 2026-11-08 at 12:20, economy.
- **tool search_flights** (2026-10-19T09:10:00): `{"flights": [{"flight_id": "FL-7700", "origin": "LAX", "destination": "SPI", "date": "2026-11-08", "departure_time": "12:20"}]}`

| argument | expected finding |
|---|---|
| (all) | supported |

**Rules:** (1) The user disambiguated ('Springfield, Illinois') and the search returned exactly one matching airport → SPI supported.

**Why:** Disambiguation happened in the request itself; the single candidate matches.

### TB-06b — expected action: `clarify`

- flying_person=Dev Rao, profile_authorized=False, now=2026-10-19T10:00:00
- **user t1:** I'm Dev Rao, DOB 1991-05-17. Book LAX to Springfield on 2026-11-08 at 12:20, economy.
- **tool search_flights** (2026-10-19T09:10:00): `{"flights": [{"flight_id": "FL-7700", "origin": "LAX", "destination": "SPI", "date": "2026-11-08", "departure_time": "12:20"}, {"flight_id": "FL-7701", "origin": "LAX", "destination": "SGF", "date": "2026-11-08", "departure_time": "12:20"}]}`

| argument | expected finding |
|---|---|
| destination_airport | **unresolved** |
| flight_id | **unresolved** |

**Rules:** (1) 'Springfield' maps to two candidate destinations (SPI and SGF) in the search result → unresolved. flight_id inherits the ambiguity. (2) Only the user can resolve which Springfield → clarify.

**Why:** Two real airports match 'Springfield' and the request never says which; the proposed SPI pick is unsupported guesswork. Ask the user.

## P07: TB-07a vs TB-07b

Proposed call (identical in both): `{"traveler_name": "Lou Amara", "passenger_dob": "1979-12-02", "origin_airport": "SEA", "destination_airport": "DFW", "date": "2026-11-25", "departure_time": "13:10", "cabin": "economy", "flight_id": "FL-8811"}`

### TB-07a — expected action: `proceed`

- flying_person=Lou Amara, profile_authorized=False, now=2026-10-19T10:00:00
- **user t1:** I'm Lou Amara, DOB 1979-12-02. Book the flight we found: SEA to DFW on 2026-11-25 at 13:10, economy.
- **tool search_flights** (2026-10-19T09:05:00): `{"flights": [{"flight_id": "FL-8811", "origin": "SEA", "destination": "DFW", "date": "2026-11-25", "departure_time": "13:10"}]}`

| argument | expected finding |
|---|---|
| (all) | supported |

**Rules:** (1) flight_id evidence is ~55min old, inside the contract's 24h validity window → supported.

**Why:** The flight quote is fresh enough to use.

### TB-07b — expected action: `retrieve`

- flying_person=Lou Amara, profile_authorized=False, now=2026-10-19T10:00:00
- **user t1:** I'm Lou Amara, DOB 1979-12-02. Book the flight we found last month: SEA to DFW on 2026-11-25 at 13:10, economy.
- **tool search_flights** (2026-09-15T09:05:00): `{"flights": [{"flight_id": "FL-8811", "origin": "SEA", "destination": "DFW", "date": "2026-11-25", "departure_time": "13:10"}]}`

| argument | expected finding |
|---|---|
| flight_id | **unresolved** |

**Rules:** (1) flight_id evidence is ~34 days old, far outside the contract's 24h validity window → the stored quote cannot be trusted → unresolved (outdated, not contradicted: the flight may still exist). (2) The fix is to re-run search_flights → retrieve.

**Why:** The only support for the flight id is a month-old search result past its 24h validity. Re-fetching may confirm the same flight or a different one — retrieve rather than execute.

## P08: TB-08a vs TB-08b

Proposed call (identical in both): `{"traveler_name": "Nadia Ferreira", "passenger_dob": "1987-04-11", "origin_airport": "MIA", "destination_airport": "LAS", "date": "2026-11-14", "departure_time": "18:05", "cabin": "economy", "flight_id": "FL-5102"}`

### TB-08a — expected action: `proceed`

- flying_person=Nadia Ferreira, profile_authorized=False, now=2026-10-19T10:00:00
- **user t1:** I'm Nadia Ferreira, DOB 1987-04-11. Book MIA to LAS on 2026-11-14 at 18:05, economy.
- **tool search_flights** (2026-10-19T08:50:00): `{"flights": [{"flight_id": "FL-5102", "origin": "MIA", "destination": "LAS", "date": "2026-11-14", "departure_time": "18:05"}]}`

| argument | expected finding |
|---|---|
| (all) | supported |

**Rules:** (1) Single instruction, no conflicting date anywhere → supported.

**Why:** The date comes straight from the only user instruction.

### TB-08b — expected action: `reject_proposed_call`

- flying_person=Nadia Ferreira, profile_authorized=False, now=2026-10-19T10:00:00
- **user t1:** I'm Nadia Ferreira, DOB 1987-04-11. Book MIA to LAS on 2026-11-14 at 18:05, economy.
- **assistant t2:** Noted: MIA to LAS, 2026-11-14, 18:05.
- **user t3:** Wait — actually make it the 15th, 2026-11-15. Everything else stays.
- **tool search_flights** (2026-10-19T08:50:00): `{"flights": [{"flight_id": "FL-5102", "origin": "MIA", "destination": "LAS", "date": "2026-11-14", "departure_time": "18:05"}, {"flight_id": "FL-5119", "origin": "MIA", "destination": "LAS", "date": "2026-11-15", "departure_time": "18:05"}]}`

| argument | expected finding |
|---|---|
| date | **contradicted** |
| flight_id | **contradicted** |

**Rules:** (1) Case precedence: the LATER user turn supersedes the earlier one for the same slot (stated explicitly here, not assumed globally). Latest value is 2026-11-15; proposed 2026-11-14 → contradicted. (2) contradicted → reject_proposed_call. Note flight_id FL-5102 is also the wrong flight for the 15th, but the deciding finding is the date.

**Why:** The user corrected the date in turn 3; the call still carries the superseded 11-14 date and a flight that only exists on the 14th. The call must not execute — replan for the 15th.

## P09: TB-09a vs TB-09b

Proposed call (identical in both): `{"traveler_name": "Owen Hale", "passenger_dob": "1996-02-14", "origin_airport": "SLC", "destination_airport": "PHX", "date": "2026-11-30", "departure_time": "07:45", "cabin": "economy", "flight_id": "FL-9305", "num_bags": 2}`

### TB-09a — expected action: `proceed`

- flying_person=Owen Hale, profile_authorized=False, now=2026-10-19T10:00:00
- **user t1:** I'm Owen Hale, DOB 1996-02-14. Book SLC to PHX on 2026-11-30 at 07:45, economy — I'll be checking 2 bags.
- **tool search_flights** (2026-10-19T09:00:00): `{"flights": [{"flight_id": "FL-9305", "origin": "SLC", "destination": "PHX", "date": "2026-11-30", "departure_time": "07:45"}]}`

| argument | expected finding |
|---|---|
| (all) | supported |

**Rules:** (1) num_bags=2 is explicitly stated ('checking 2 bags') → supported.

**Why:** The bag count is stated, not assumed.

### TB-09b — expected action: `reject_proposed_call`

- flying_person=Owen Hale, profile_authorized=False, now=2026-10-19T10:00:00
- **user t1:** I'm Owen Hale, DOB 1996-02-14. Book SLC to PHX on 2026-11-30 at 07:45, economy — traveling light this time.
- **tool search_flights** (2026-10-19T09:00:00): `{"flights": [{"flight_id": "FL-9305", "origin": "SLC", "destination": "PHX", "date": "2026-11-30", "departure_time": "07:45"}]}`

| argument | expected finding |
|---|---|
| num_bags | **missing** |

**Rules:** (1) num_bags is optional with documented default 0; 'traveling light' supplies no count. No source supports 2 → missing. (2) Unsupported optional argument → reject_proposed_call (omit it and the documented default applies).

**Why:** The value 2 is an unsupported assumption; it even plausibly conflicts with 'traveling light'. The corrected call drops the argument.

## P10: TB-10a vs TB-10b

Proposed call (identical in both): `{"traveler_name": "June Park", "passenger_dob": "1990-10-08", "origin_airport": "SFO", "destination_airport": "AUS", "date": "2026-12-02", "departure_time": "15:30", "cabin": "economy", "flight_id": "FL-1207"}`

### TB-10a — expected action: `proceed`

- flying_person=June Park, profile_authorized=True, now=2026-10-19T10:00:00
- **user t1:** I'm June Park, DOB 1990-10-08. Book a flight from my usual airport to AUS on 2026-12-02 at 15:30, economy. Go ahead and use my saved profile.
- **tool lookup_traveler_profile** (2026-10-19T09:45:00): `{"full_name": "June Park", "home_airport": "SFO"}`
- **tool search_flights** (2026-10-19T09:50:00): `{"flights": [{"flight_id": "FL-1207", "origin": "SFO", "destination": "AUS", "date": "2026-12-02", "departure_time": "15:30"}]}`

| argument | expected finding |
|---|---|
| (all) | supported |

**Rules:** (1) 'My usual airport' is a valid deference only because the profile lookup is authorized and home_airport=SFO resolves it.

**Why:** The deference to the profile is explicit and authorized; home_airport supplies SFO.

### TB-10b — expected action: `clarify`

- flying_person=June Park, profile_authorized=False, now=2026-10-19T10:00:00
- **user t1:** I'm June Park, DOB 1990-10-08. Book a flight from my usual airport to AUS on 2026-12-02 at 15:30, economy.
- **tool search_flights** (2026-10-19T09:50:00): `{"flights": [{"flight_id": "FL-1207", "origin": "SFO", "destination": "AUS", "date": "2026-12-02", "departure_time": "15:30"}, {"flight_id": "FL-1402", "origin": "OAK", "destination": "AUS", "date": "2026-12-02", "departure_time": "15:30"}]}`

| argument | expected finding |
|---|---|
| origin_airport | **unresolved** |
| flight_id | **unresolved** |

**Rules:** (1) 'My usual airport' cannot be resolved: no profile authorization and no explicit airport in the conversation. Two candidates (SFO, OAK) exist in the search result → unresolved. (2) The user must say which airport (or authorize the lookup) → clarify. flight_id inherits the ambiguity.

**Why:** SFO was assumed, not evidenced — without profile access the 'usual airport' is unknowable and two airports fit. Ask.
