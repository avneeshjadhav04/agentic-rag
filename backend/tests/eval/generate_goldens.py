"""Generate a golden Q&A dataset from the live Chroma store using DeepEval's Synthesizer.

Usage:
    cd backend
    python -m tests.eval.generate_goldens

This reads chunks already ingested into your Chroma vector store, feeds them to
DeepEval's Synthesizer to produce ~20 question/answer/context goldens, and writes
golden_dataset.json next to this file.

The dataset uses the *evaluation* provider as the synthesizer LLM (so synthetic
Q&A generation is decoupled from the generation model being evaluated).

Curate the output before committing — these goldens are the ground truth for all
RAG metrics in test_rag_e2e.py and test_rag_components.py.
"""
import json
import os
import sys
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent / "golden_dataset.json"


def _env(name: str, fallback: str = "") -> str:
    return os.environ.get(name, fallback)


def load_contexts_from_chroma() -> list[str]:
    """Read text chunks from the live Chroma store."""
    from app.models.factory import get_embeddings
    from app.vectorstore.chroma_store import ChromaStore

    emb_cfg = {
        "base_url": _env("DEFAULT_EMBEDDING_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        "model": _env("DEFAULT_EMBEDDING_MODEL", "nvidia/nemotron-3-embed-1b"),
        "api_key": _env("DEFAULT_EMBEDDING_API_KEY", ""),
    }
    embeddings = get_embeddings(emb_cfg["base_url"], emb_cfg["model"], emb_cfg["api_key"])
    store = ChromaStore(embeddings=embeddings)
    collection = store._get_store()._collection
    results = collection.get(include=["documents"])
    docs = results.get("documents", [])
    if not docs:
        print("Chroma store is empty. Ingest documents first (via the UI or API).")
        sys.exit(1)
    print(f"Loaded {len(docs)} chunks from Chroma.")
    return docs


def build_synthesizer():
    """Construct a DeepEval Synthesizer using the evaluation provider's LLM."""
    from deepeval.models import DeepEvalBaseLLM
    from deepeval.synthesizer import Synthesizer
    from langchain_openai import ChatOpenAI

    eval_cfg = {
        "base_url": _env("DEFAULT_EVALUATION_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        "model": _env("DEFAULT_EVALUATION_MODEL", "openai/gpt-oss-20b"),
        "api_key": _env("DEFAULT_EVALUATION_API_KEY", ""),
    }

    class NvidiaNimSynthesizerLLM(DeepEvalBaseLLM):
        def __init__(self):
            self._model_name = eval_cfg["model"]
            self._client = ChatOpenAI(
                base_url=eval_cfg["base_url"],
                model=eval_cfg["model"],
                api_key=eval_cfg["api_key"] or "dummy",
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

    return Synthesizer(model=NvidiaNimSynthesizerLLM())


def main():
    contexts = load_contexts_from_chroma()
    synthesizer = build_synthesizer()

    print("Synthesizing goldens (this may take a few minutes)...")
    synthesizer.generate_goldens_from_docs(
        contexts=contexts,
        num_goldens=20,
    )

    goldens = []
    for golden in synthesizer.goldens:
        goldens.append({
            "input": golden.input,
            "expected_output": golden.expected_output,
            "expected_context": list(golden.context) if golden.context else [],
        })

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(goldens, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(goldens)} goldens to {OUTPUT_PATH}")
    print("Review and curate before committing.")


if __name__ == "__main__":
    main()