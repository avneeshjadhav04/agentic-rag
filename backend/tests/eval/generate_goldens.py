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
import sys
from pathlib import Path

from app.eval.runner import embedding_config, evaluation_config

OUTPUT_PATH = Path(__file__).parent / "golden_dataset.json"


def load_contexts_from_chroma() -> list[str]:
    """Read text chunks from the live Chroma store."""
    from app.models.factory import get_embeddings
    from app.vectorstore.chroma_store import ChromaStore

    emb_cfg = embedding_config()
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
    from deepeval.synthesizer import Synthesizer

    from app.eval.runner import NvidiaNimJudge

    eval_cfg = evaluation_config()
    judge = NvidiaNimJudge(eval_cfg["base_url"], eval_cfg["model"], eval_cfg["api_key"])
    return Synthesizer(model=judge)


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