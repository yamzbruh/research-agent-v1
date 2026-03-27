import os
import time
from typing import List, TypedDict

import requests
from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph
from tavily import TavilyClient
import anthropic


class ResearchState(TypedDict):
    topic: str
    sources: List[str]
    summaries: List[str]
    awaiting_approval: bool


def _is_url_alive(url: str, timeout: int = 10) -> bool:
    """Return True if URL responds with HTTP 200."""
    try:
        response = requests.get(url, timeout=timeout, allow_redirects=True)
        return response.status_code == 200
    except requests.RequestException:
        return False


def search_web(state: ResearchState) -> ResearchState:
    topic = state["topic"]
    tavily_api_key = os.getenv("TAVILY_API_KEY", "")
    if not tavily_api_key:
        raise ValueError("Missing TAVILY_API_KEY in environment.")

    tavily = TavilyClient(api_key=tavily_api_key)

    target_count = 5
    valid_sources: List[str] = []
    seen_urls = set()
    search_depth = "advanced"
    max_search_calls = 8
    search_calls = 0

    while len(valid_sources) < target_count and search_calls < max_search_calls:
        search_calls += 1
        response = tavily.search(
            query=f"{topic} latest reliable sources",
            max_results=10,
            search_depth=search_depth,
        )
        results = response.get("results", [])

        for item in results:
            if len(valid_sources) >= target_count:
                break
            url = (item or {}).get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            if _is_url_alive(url):
                valid_sources.append(url)

    if len(valid_sources) < target_count:
        raise RuntimeError(
            f"Only found {len(valid_sources)} live sources for topic '{topic}' after retries."
        )

    return {
        "topic": topic,
        "sources": valid_sources,
        "summaries": [],
        "awaiting_approval": False,
    }


def summarize(state: ResearchState) -> ResearchState:
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not anthropic_api_key:
        raise ValueError("Missing ANTHROPIC_API_KEY in environment.")
    tavily_api_key = os.getenv("TAVILY_API_KEY", "")
    if not tavily_api_key:
        raise ValueError("Missing TAVILY_API_KEY in environment.")

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    tavily = TavilyClient(api_key=tavily_api_key)

    summarized_sources: List[str] = []
    summaries: List[str] = []
    for url in state["sources"][:3]:
        try:
            result = tavily.extract(urls=[url])
            extract_results = (result or {}).get("results", [])
            extracted_text = ""
            if extract_results:
                first_item = extract_results[0] or {}
                extracted_text = (first_item.get("raw_content") or first_item.get("content") or "").strip()
            if not extracted_text:
                continue
        except Exception:
            continue

        prompt = (
            "Summarize the following source content in exactly 2 sentences. "
            "Be factual and concise.\n\n"
            f"Source content:\n{extracted_text}"
        )

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        time.sleep(10)
        text_chunks = [
            block.text for block in message.content if getattr(block, "type", "") == "text"
        ]
        summary = " ".join(text_chunks).strip()
        summarized_sources.append(url)
        summaries.append(summary)

    return {
        "topic": state["topic"],
        "sources": summarized_sources,
        "summaries": summaries,
        "awaiting_approval": True,
    }


def await_approval(state: ResearchState) -> ResearchState:
    approved_sources: List[str] = []
    approved_summaries: List[str] = []

    print("\nReview each source and type 'approve' or 'reject'.\n")
    for idx, (source, summary) in enumerate(zip(state["sources"], state["summaries"]), start=1):
        print(f"[{idx}] Source: {source}")
        print(f"    Summary: {summary}\n")
        while True:
            decision = input("Decision (approve/reject): ").strip().lower()
            if decision in {"approve", "reject"}:
                break
            print("Please type exactly 'approve' or 'reject'.")

        if decision == "approve":
            approved_sources.append(source)
            approved_summaries.append(summary)
        print()

    return {
        "topic": state["topic"],
        "sources": approved_sources,
        "summaries": approved_summaries,
        "awaiting_approval": False,
    }


def build_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("search_web", search_web)
    graph.add_node("summarize", summarize)
    graph.add_node("await_approval", await_approval)

    graph.add_edge(START, "search_web")
    graph.add_edge("search_web", "summarize")
    graph.add_edge("summarize", "await_approval")
    graph.add_edge("await_approval", END)

    return graph.compile()


def main() -> None:
    load_dotenv()
    topic = input("Enter a research topic: ").strip()
    if not topic:
        print("Topic cannot be empty.")
        return

    app = build_graph()
    initial_state: ResearchState = {
        "topic": topic,
        "sources": [],
        "summaries": [],
        "awaiting_approval": False,
    }

    final_state = app.invoke(initial_state)

    print("\n=== Final Approved Report ===")
    approved_sources = final_state["sources"]
    if not approved_sources:
        print("No sources were approved.")
        return

    for i, src in enumerate(approved_sources, start=1):
        print(f"{i}. {src}")


if __name__ == "__main__":
    main()
