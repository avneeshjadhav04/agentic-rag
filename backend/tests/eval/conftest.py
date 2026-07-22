"""Pytest fixtures for the DeepEval RAG evaluation harness.

Reads provider configuration from environment variables (the same
DEFAULT_GENERATION_* / DEFAULT_EVALUATION_* / DEFAULT_EMBEDDING_* vars
used by the backend's config/defaults.py) and constructs:

  * a DeepEval-compatible judge LLM from the *evaluation* provider
  * a compiled Agentic RAG LangGraph using the *generation* + *embedding* providers
  * a loaded golden dataset (backend/tests/eval/golden_dataset.json)
"""
import json
import os
from pathlib import Path
from typing import List, Optional

import pytest
from deepeval.models import DeepEvalBaseLLM
from langchain_openai import ChatOpenAI

from app.agents.graph import build_agentic_rag_graph
from app.models.factory import get_embeddings, get_generation_llm
from app.vectorstore.chroma_store import ChromaStore

EVAL_DIR = Path(__file__).parent
GOLDEN_DATASET_PATH = EVAL_DIR / "golden_dataset.json"


def _env(name: str, fallback: str = "") -> str:
    return os.environ.get(name, fallback)


def _generation_config() -> dict:
    return {
        "base_url": _env("DEFAULT_GENERATION_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        "model": _env("DEFAULT_GENERATION_MODEL", "openai/gpt-oss-20b"),
        "api_key": _env("DEFAULT_GENERATION_API_KEY", ""),
    }


def _evaluation_config() -> dict:
    return {
        "base_url": _env("DEFAULT_EVALUATION_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        "model": _env("DEFAULT_EVALUATION_MODEL", "openai/gpt-oss-20b"),
        "api_key": _env("DEFAULT_EVALUATION_API_KEY", ""),
    }


def _embedding_config() -> dict:
    return {
        "base_url": _env("DEFAULT_EMBEDDING_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        "model": _env("DEFAULT_EMBEDDING_MODEL", "nvidia/nemotron-3-embed-1b"),
        "api_key": _env("DEFAULT_EMBEDDING_API_KEY", ""),
    }


class NvidiaNimJudge(DeepEvalBaseLLM):
    """DeepEval judge LLM wrapping an OpenAI-compatible endpoint (NVIDIA NIM default).

    Uses the *evaluation* provider config so the judge is independent of the
    generation model that produced the answers being scored.
    """

    def __init__(self, base_url: str, model: str, api_key: str):
        self._model_name = model
        self._client = ChatOpenAI(
            base_url=base_url,
            model=model,
            api_key=api_key or "dummy",
            temperature=0.0,
            streaming=False,
        )

    def load_model(self):
        return self._client

    def get_model_name(self) -> str:
        return self._model_name

    def generate(self, prompt: str) -> str:
        response = self._client.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    async def a_generate(self, prompt: str) -> str:
        response = await self._client.ainvoke(prompt)
        return response.content if hasattr(response, "content") else str(response)


@pytest.fixture(scope="session")
def judge_llm() -> NvidiaNimJudge:
    cfg = _evaluation_config()
    return NvidiaNimJudge(cfg["base_url"], cfg["model"], cfg["api_key"])


@pytest.fixture(scope="session")
def rag_graph():
    """Compiled Agentic RAG graph using the generation + embedding providers."""
    gen = _generation_config()
    emb = _embedding_config()
    llm = get_generation_llm(gen["base_url"], gen["model"], gen["api_key"])
    embeddings = get_embeddings(emb["base_url"], emb["model"], emb["api_key"])
    vector_store = ChromaStore(embeddings=embeddings)
    return build_agentic_rag_graph(llm, embeddings, vector_store)


@pytest.fixture(scope="session")
def golden_dataset() -> List[dict]:
    """Load the golden Q&A dataset produced by generate_goldens.py."""
    if not GOLDEN_DATASET_PATH.exists():
        pytest.skip(
            f"Golden dataset not found at {GOLDEN_DATASET_PATH}. "
            "Run `python -m tests.eval.generate_goldens` first."
        )
    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        pytest.skip("Golden dataset is empty.")
    return data


@pytest.fixture
def golden(request, golden_dataset) -> dict:
    """Single golden, selected by index via --golden-idx or 0 by default."""
    idx = getattr(request, "param", 0)
    if idx >= len(golden_dataset):
        pytest.skip(f"Golden index {idx} out of range (dataset has {len(golden_dataset)} entries).")
    return golden_dataset[idx]


def run_graph_for_question(graph, question: str) -> dict:
    """Invoke the RAG graph for a single question and return the final state."""
    from app.agents.state import AgentState
    state: AgentState = {
        "question": question,
        "messages": [],
        "documents": [],
        "web_search_urls": [],
        "generation": None,
        "trace": [],
        "steps": 0,
        "web_search_enabled": False,
        "max_loops": 3,
    }
    return graph.invoke(state)