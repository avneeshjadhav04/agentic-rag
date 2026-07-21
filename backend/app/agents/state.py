"""Shared state for the LangGraph agent workflow."""
from typing import Annotated, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    question: str
    messages: Annotated[list, add_messages]
    documents: list[dict]
    web_search_urls: list[str]
    generation: Optional[str]
    trace: list[dict]
    steps: int
    web_search_enabled: bool
    max_loops: int
    refined_question: Optional[str]
