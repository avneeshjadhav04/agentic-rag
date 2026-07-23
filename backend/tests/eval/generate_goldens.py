"""Generate a golden Q&A dataset from the live Chroma store using DeepEval's Synthesizer.

Usage:
    cd backend
    python -m tests.eval.generate_goldens

This is a thin CLI wrapper around app.eval.runner.generate_goldens_streaming,
which is also called by the POST /api/eval/generate-goldens SSE endpoint so the
CLI and the UI share the same logic.

The dataset uses the *evaluation* provider as the synthesizer LLM (so synthetic
Q&A generation is decoupled from the generation model being evaluated).

Curate the output before committing — these goldens are the ground truth for all
RAG metrics in test_rag_e2e.py and test_rag_components.py.
"""
import sys

from app.eval.runner import embedding_config, evaluation_config, generate_goldens_streaming


def main():
    emb_cfg = embedding_config()
    eval_cfg = evaluation_config()

    def progress_callback(result: dict) -> None:
        stage = result.get("stage", "")
        message = result.get("message", "")
        print(f"[{stage}] {message}")

    try:
        result = generate_goldens_streaming(emb_cfg, eval_cfg, progress_callback=progress_callback)
        print(f"Wrote {result['count']} goldens to {result['path']}")
        print("Review and curate before committing.")
    except ValueError as e:
        print(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()