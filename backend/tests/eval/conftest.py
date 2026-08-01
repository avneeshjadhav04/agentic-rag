"""Pytest fixtures for the DeepEval RAG evaluation harness.

All shared logic (NvidiaNimJudge, config helpers, run_graph_for_question) lives
in app.eval.runner so it can be reused by both the pytest tests and the live
SSE endpoint. This file wraps them as pytest fixtures.
"""
import pytest

from app.eval.runner import (
    NvidiaNimJudge,
    build_rag_graph,
    embedding_config,
    evaluation_config,
    generation_config,
    load_golden_dataset,
    run_graph_for_question,
)


@pytest.fixture(scope="session")
def judge_llm() -> NvidiaNimJudge:
    cfg = evaluation_config()
    return NvidiaNimJudge(cfg["base_url"], cfg["model"], cfg["api_key"])


@pytest.fixture(scope="session")
def rag_graph():
    """Compiled Agentic RAG graph using the generation + embedding providers."""
    return build_rag_graph(generation_config(), embedding_config())


@pytest.fixture(scope="session")
def golden_dataset() -> list[dict]:
    """Load the golden Q&A dataset (golden_dataset.json)."""
    try:
        return load_golden_dataset()
    except (FileNotFoundError, ValueError) as e:
        pytest.skip(str(e))