"""A small, clearly-labeled toy fixture for pipeline testing.

This is NOT a benchmark. It exists so the full pipeline (splits, catalog
scenarios, retrieval, abstention, metrics, reporting) can be exercised
quickly and deterministically without any network access or model
download, and so unit tests do not depend on ToolRet being downloaded.

Results computed on this fixture must never be reported as benchmark
findings (see README.md and docs/dataset.md).
"""
from __future__ import annotations

from tool_routing.data.schema import Request, Tool

SOURCE = "toy"

# Three "tool families" by rough API provider, used to check tool-family
# separation in split-building. Each family has 2-4 tools with genuinely
# different functionality, plus near-duplicate "sibling" tools that are
# useful as similar distractors in catalog scenarios.
_TOOLS_RAW = [
    # weather family
    ("weather_current", "get_current_weather", "Get the current weather conditions for a city.", "weather"),
    ("weather_forecast", "get_weather_forecast", "Get a multi-day weather forecast for a city.", "weather"),
    ("weather_alerts", "get_weather_alerts", "Get active severe weather alerts for a region.", "weather"),
    ("weather_historical", "get_historical_weather", "Get historical weather observations for a city and date.", "weather"),
    # finance family
    ("finance_stock_quote", "get_stock_quote", "Get the latest stock price quote for a ticker symbol.", "finance"),
    ("finance_currency_convert", "convert_currency", "Convert an amount from one currency to another using live rates.", "finance"),
    ("finance_company_profile", "get_company_profile", "Get company profile information for a stock ticker.", "finance"),
    # calendar/productivity family
    ("calendar_create_event", "create_calendar_event", "Create a new event on a user's calendar.", "calendar"),
    ("calendar_list_events", "list_calendar_events", "List upcoming events on a user's calendar.", "calendar"),
    ("calendar_delete_event", "delete_calendar_event", "Delete an existing event from a user's calendar.", "calendar"),
    # translation family
    ("translate_text", "translate_text", "Translate text from one language to another.", "translation"),
    ("translate_detect_lang", "detect_language", "Detect the language of a piece of text.", "translation"),
    # distractor pool (held out from the main catalog; used only for
    # "similar distractors added" scenarios)
    ("weather_marine", "get_marine_forecast", "Get a marine weather forecast (wind, waves) for coastal coordinates.", "weather"),
    ("finance_crypto_quote", "get_crypto_quote", "Get the latest price quote for a cryptocurrency symbol.", "finance"),
    ("calendar_update_event", "update_calendar_event", "Update the time or details of an existing calendar event.", "calendar"),
]

# Pool of tool_ids that are NOT part of the default catalog and are used
# only as the reserved "similar distractors added" pool.
DISTRACTOR_POOL_IDS = {"weather_marine", "finance_crypto_quote", "calendar_update_event"}

_PARAMS_BY_FAMILY = {
    "weather": {"city": {"type": "string"}},
    "finance": {"symbol": {"type": "string"}},
    "calendar": {"event_id": {"type": "string"}},
    "translation": {"text": {"type": "string"}},
}


def load_tools() -> list[Tool]:
    tools = []
    for tool_id, name, description, family in _TOOLS_RAW:
        tools.append(
            Tool(
                tool_id=f"{SOURCE}_{tool_id}",
                name=name,
                description=description,
                parameters=_PARAMS_BY_FAMILY.get(family, {}),
                source_dataset=SOURCE,
                tool_family=family,
                raw={"tool_id": tool_id, "family": family},
            )
        )
    return tools


_QUERIES_RAW = [
    ("q_weather_1", "What's the weather like in Paris right now?", ["weather_current"]),
    ("q_weather_2", "Will it rain in Boston over the next five days?", ["weather_forecast"]),
    ("q_weather_3", "Are there any severe weather warnings for Miami?", ["weather_alerts"]),
    ("q_weather_4", "What was the weather in Chicago last July 4th?", ["weather_historical"]),
    ("q_weather_5", "Tell me the current temperature in Tokyo.", ["weather_current"]),
    ("q_finance_1", "What is Apple's current stock price?", ["finance_stock_quote"]),
    ("q_finance_2", "Convert 100 US dollars to Japanese yen.", ["finance_currency_convert"]),
    ("q_finance_3", "Give me a company profile for Tesla.", ["finance_company_profile"]),
    ("q_finance_4", "How much is 50 euros in British pounds?", ["finance_currency_convert"]),
    ("q_calendar_1", "Schedule a meeting with my team tomorrow at 10am.", ["calendar_create_event"]),
    ("q_calendar_2", "What meetings do I have this week?", ["calendar_list_events"]),
    ("q_calendar_3", "Cancel my 3pm dentist appointment.", ["calendar_delete_event"]),
    ("q_translate_1", "Translate 'good morning' into Spanish.", ["translate_text"]),
    ("q_translate_2", "What language is this sentence written in?", ["translate_detect_lang"]),
    # near-duplicate variants of q_weather_1, used to test split grouping
    ("q_weather_1_dup1", "What's the weather like in Paris right now?", ["weather_current"]),
    ("q_weather_1_dup2", "what's the weather like in paris right now??", ["weather_current"]),
    # a query with two genuinely alternative valid tools (OR semantics)
    ("q_finance_5", "I need Apple's latest price information.", ["finance_stock_quote", "finance_company_profile"]),
    ("q_calendar_4", "Add a dentist appointment to my calendar for Friday.", ["calendar_create_event"]),
    ("q_translate_3", "How do you say 'thank you' in French?", ["translate_text"]),
    ("q_weather_6", "Give me the forecast for Seattle this weekend.", ["weather_forecast"]),
]


def load_requests() -> list[Request]:
    requests = []
    for query_id, text, valid_tools in _QUERIES_RAW:
        requests.append(
            Request(
                query_id=f"{SOURCE}_{query_id}",
                query_text=text,
                known_valid_tool_ids=tuple(f"{SOURCE}_{t}" for t in valid_tools),
                source_dataset=SOURCE,
                answerability_review_status="answerable",
                raw={"query_id": query_id},
            )
        )
    return requests


def load_toy_dataset() -> tuple[list[Tool], list[Request]]:
    """Return (tools, requests) for the toy fixture.

    ``tools`` excludes the held-out distractor pool; use
    ``load_distractor_pool_tools`` to fetch it separately.
    """
    all_tools = load_tools()
    main_tools = [t for t in all_tools if t.raw["tool_id"] not in DISTRACTOR_POOL_IDS]
    return main_tools, load_requests()


def load_distractor_pool_tools() -> list[Tool]:
    all_tools = load_tools()
    return [t for t in all_tools if t.raw["tool_id"] in DISTRACTOR_POOL_IDS]
