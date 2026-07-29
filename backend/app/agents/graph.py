"""LangGraph assembly for the multi-agent RAG workflow (subagents pattern).

Topology:
    START → main_agent ↔ (research, draft_answer, finalize_answer tools)
                      ↓ (generation set via finalize_answer)
               quality_check (deterministic node)
                      ↓
              pass / max_loops → END
              fail + retries   → QualityFeedbackMessage → main_agent (retry)

The main agent is a ``create_agent`` instance with three tools backed by
research and writer subagents.  The quality_check is a deterministic
StateGraph node that grades ``state["generation"]`` against
``state["documents"]`` using ``with_structured_output``.
"""
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.vectorstore.chroma_store import ChromaStore

from .nodes import (
    main_agent_factory,
    quality_check_node_factory,
    route_after_main,
    route_after_quality,
)
from .state import WorkflowState

try:
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover
    END = "__end__"
    START = "__start__"
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

    main_agent = main_agent_factory(llm, vector_store, k=retrieval_k, web_search_enabled=web_search_enabled)
    quality_check = quality_check_node_factory(llm)

    workflow = StateGraph(WorkflowState)

    workflow.add_node("main_agent", main_agent)
    workflow.add_node("quality_check", quality_check)

    workflow.add_edge(START, "main_agent")
    workflow.add_conditional_edges(
        "main_agent",
        route_after_main,
        {"main_agent": "main_agent", "quality_check": "quality_check"},
    )
    workflow.add_conditional_edges(
        "quality_check",
        route_after_quality,
        {"main_agent": "main_agent", "end": END},
    )

    return workflow.compile()