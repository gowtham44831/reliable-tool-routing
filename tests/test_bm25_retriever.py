from tool_routing.data.schema import Tool
from tool_routing.retrieval.bm25 import BM25Retriever, tokenize


def test_tokenize_is_deterministic_and_lowercases():
    assert tokenize("Get the Current Weather!!") == ["get", "the", "current", "weather"]
    assert tokenize("Get the Current Weather!!") == tokenize("get the current weather")


def test_bm25_ranks_relevant_tool_first():
    tools = [
        Tool("t1", "get_weather", "Get the current weather for a city.", source_dataset="x"),
        Tool("t2", "send_email", "Send an email to a recipient.", source_dataset="x"),
    ]
    retriever = BM25Retriever()
    retriever.prepare_catalog("c1", tools)
    result = retriever.rank("c1", "what is the weather in paris", top_k=2)
    assert result.top1_tool_id == "t1"
    assert result.margin is not None and result.margin >= 0


def test_bm25_empty_catalog_returns_empty_result():
    retriever = BM25Retriever()
    retriever.prepare_catalog("empty", [])
    result = retriever.rank("empty", "anything", top_k=5)
    assert result.tool_ids == ()
    assert result.scores == ()
    assert result.top1_tool_id is None
    assert result.margin is None


def test_bm25_catalog_caching_is_keyed_by_catalog_id():
    retriever = BM25Retriever()
    tools_a = [Tool("t1", "a", "alpha description", source_dataset="x")]
    tools_b = [Tool("t2", "b", "beta description", source_dataset="x")]
    retriever.prepare_catalog("a", tools_a)
    retriever.prepare_catalog("b", tools_b)
    assert retriever.rank("a", "alpha").top1_tool_id == "t1"
    assert retriever.rank("b", "beta").top1_tool_id == "t2"
