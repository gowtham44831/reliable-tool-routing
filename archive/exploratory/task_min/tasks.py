"""Task set — machine-checkable constraints kept SEPARATE from
privacy permissions. `private_fields` are what the request would
over-share; `constraints` are the machine-checkable task spec
evaluated against the TRUE (local, private) origin.

exact_required=True marks tasks where the precise origin is itself
the payload — minimization and task preservation are in direct
conflict; stopping/clarifying is the correct outcome, and such tasks
are counted as BLOCKED, never as successful completions.
"""

from dataset import USER_PRIVATE

TASKS = [
    {
        "id": "T1_grid_works",
        "desc": "wheelchair cafés <= $15 within 3 km of home",
        "call": {"tool": "location_search",
                 "args": {"category": "cafe",
                          "lat": USER_PRIVATE["home_lat"],
                          "lon": USER_PRIVATE["home_lon"],
                          "radius_km": 3.0,
                          "wheelchair_required": True,
                          "max_price": 15,
                          "user_name": USER_PRIVATE["name"],
                          "note": "from my home, usual spot"},
                 "private_fields": ["lat", "lon", "user_name", "note"]},
        "constraints": {"category": "cafe", "wheelchair": True,
                        "max_price": 15, "max_dist_km": 3.0},
        "exact_required": False,
        "granularity": "grid_1km",
    },
    {
        "id": "T2_grid_breaks",
        "desc": "pharmacy within 0.5 km of home (tight radius)",
        "call": {"tool": "location_search",
                 "args": {"category": "pharmacy",
                          "lat": USER_PRIVATE["home_lat"],
                          "lon": USER_PRIVATE["home_lon"],
                          "radius_km": 0.5,
                          "user_name": USER_PRIVATE["name"],
                          "note": "home"},
                 "private_fields": ["lat", "lon", "user_name", "note"]},
        "constraints": {"category": "pharmacy", "max_dist_km": 0.5},
        "exact_required": False,
        "granularity": "grid_5km",   # annotation-level coarsening
    },
    {
        "id": "T3_exact_payload",
        "desc": "support group nearest my exact home address",
        "call": {"tool": "location_search",
                 "args": {"category": "support_group",
                          "lat": USER_PRIVATE["home_lat"],
                          "lon": USER_PRIVATE["home_lon"],
                          "radius_km": 0.5,
                          "user_name": USER_PRIVATE["name"],
                          "note": "Harbor group for Arden"},
                 "private_fields": ["lat", "lon", "user_name", "note"]},
        "constraints": {"category": "support_group",
                        "max_dist_km": 0.5},
        "exact_required": True,      # origin IS the payload
        "granularity": "city",
    },
    {
        "id": "T4_multi_constraint",
        "desc": "restaurants <= $20 wheelchair within 2.5 km",
        "call": {"tool": "location_search",
                 "args": {"category": "restaurant",
                          "lat": USER_PRIVATE["home_lat"],
                          "lon": USER_PRIVATE["home_lon"],
                          "radius_km": 2.5,
                          "wheelchair_required": True,
                          "max_price": 20,
                          "user_name": USER_PRIVATE["name"],
                          "note": "dinner w/ mum"},
                 "private_fields": ["lat", "lon", "user_name", "note"]},
        "constraints": {"category": "restaurant", "wheelchair": True,
                        "max_price": 20, "max_dist_km": 2.5},
        "exact_required": False,
        "granularity": "grid_1km",
    },
    {
        "id": "T5_city_breaks",
        "desc": "clinic within 2 km of home",
        "call": {"tool": "location_search",
                 "args": {"category": "clinic",
                          "lat": USER_PRIVATE["home_lat"],
                          "lon": USER_PRIVATE["home_lon"],
                          "radius_km": 2.0,
                          "user_name": USER_PRIVATE["name"],
                          "note": "my clinic search"},
                 "private_fields": ["lat", "lon", "user_name", "note"]},
        "constraints": {"category": "clinic", "max_dist_km": 2.0},
        "exact_required": False,
        "granularity": "city",       # over-coarse: annotation bug
    },
]
