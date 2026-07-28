"""LangGraph assembly for the multi-agent RAG workflow.

Topology:
    supervisor → researcher ↔ research_tools → supervisor
    supervisor → writer → quality_check → supervisor (or END)

The supervisor is an LLM that decides which sub-agent to call. The researcher
is a tool-calling ReAct agent (vector_search, web_fetch, handoff). The writer
synthesizes a grounded answer. The quality_check critic grades the answer and
routes feedback back to the supervisor on failure.
"""
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.vectorstore.chroma_store import ChromaStore

from .nodes import (
    quality_check_node_factory,
    research_tools_node_factory,
    researcher_node_factory,
    route_after_quality,
    route_after_researcher,
    route_after_supervisor,
    supervisor_node_factory,
    writer_node_factory,
)
from .state import AgentState

try:
    from langgraph.graph import END, StateGraph
except ImportError:  # pragma: no cover
    END = "__end__"
    StateGraph = None


def build_agentic_rag_graph(
    llm: ChatOpenAI,
    embeddings: OpenAIEmbeddings,
    vector_store: ChromaStore,
    retrieval_k: int = 4,
    web_search_enabled: bool = False,
):
    if StateGraph is None:
        raise RuntimeError("langgraph is not installed")

    workflow = StateGraph(AgentState)

    workflow.add_node("supervisor", supervisor_node_factory(llm))
    workflow.add_node("researcher", researcher_node_factory(
        llm,
        allow_web_fetch=web_search_enabled,
    ))
    workflow.add_node("research_tools", research_tools_node_factory(vector_store, llm, k=retrieval_k))
    workflow.add_node("writer", writer_node_factory(llm))
    workflow.add_node("quality_check", quality_check_node_factory(llm))

    workflow.set_entry_point("supervisor")
    workflow.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {"researcher": "researcher", "writer": "writer", "end": END},
    )
    workflow.add_conditional_edges(
        "researcher",
        route_after_researcher,
        {"research_tools": "research_tools", "supervisor": "supervisor"},
    )
    workflow.add_edge("research_tools", "researcher")
    workflow.add_edge("writer", "quality_check")
    workflow.add_conditional_edges(
        "quality_check",
        route_after_quality,
        {"supervisor": "supervisor", "end": END},
    )

    return workflow.compile()