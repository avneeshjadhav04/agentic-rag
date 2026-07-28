"""Shared state for the LangGraph multi-agent RAG workflow."""
from typing import Annotated, Optional

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    question: str
    messages: Annotated[list, add_messages]
    documents: list[dict]
    generation: Optional[str]
    trace: list[dict]
    steps: int
    web_search_enabled: bool
    max_loops: int
    quality_passed: bool
    next_agent: Optional[str]
    pending_tool: Optional[str]
    pending_args: Optional[dict]
    tool_call_count: int
    tool_call_id: Optional[str]
    quality_feedback: Optional[str]