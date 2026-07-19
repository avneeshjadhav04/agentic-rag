"""LangGraph assembly for the Agentic RAG workflow."""
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.vectorstore.chroma_store import ChromaStore

from .nodes import (
    fetch_urls_node,
    generate_node_factory,
    grade_documents_node_factory,
    propose_urls_node_factory,
    quality_check_node_factory,
    retrieve_node_factory,
    route_after_grading,
    route_after_quality,
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
):
    if StateGraph is None:
        raise RuntimeError("langgraph is not installed")

    workflow = StateGraph(AgentState)

    workflow.add_node("retrieve", retrieve_node_factory(vector_store, k=retrieval_k))
    workflow.add_node("grade_documents", grade_documents_node_factory(llm))
    workflow.add_node("propose_urls", propose_urls_node_factory(llm))
    workflow.add_node("fetch_urls", fetch_urls_node)
    workflow.add_node("generate", generate_node_factory(llm))
    workflow.add_node("quality_check", quality_check_node_factory(llm))

    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "grade_documents")
    workflow.add_conditional_edges(
        "grade_documents",
        route_after_grading,
        {"generate": "generate", "propose_urls": "propose_urls"},
    )
    workflow.add_edge("propose_urls", "fetch_urls")
    workflow.add_edge("fetch_urls", "generate")
    workflow.add_edge("generate", "quality_check")
    workflow.add_conditional_edges(
        "quality_check",
        route_after_quality,
        {"end": END},
    )

    return workflow.compile()
