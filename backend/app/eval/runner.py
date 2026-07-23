"""Programmatic DeepEval RAG runner shared by the pytest harness and the live SSE endpoint.

This module owns the canonical implementations of:
  - NvidiaNimJudge (DeepEvalBaseLLM wrapping an OpenAI-compatible endpoint)
  - provider config helpers (generation / evaluation / embedding)
  - run_graph_for_question (invoke the Agentic RAG graph for one question)
  - run_evals_streaming (iterate goldens, score with 4 RAG metrics, emit progress)
  - load_latest_results (read the most recent .deepeval/*.json from disk)
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
)
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase
from langchain_openai import ChatOpenAI

from app.agents.graph import build_agentic_rag_graph
from app.models.factory import get_embeddings, get_generation_llm
from app.vectorstore.chroma_store import ChromaStore

EVAL_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "eval"
GOLDEN_DATASET_PATH = EVAL_DIR / "golden_dataset.json"
DEFAULT_RESULTS_DIR = str(Path(__file__).resolve().parent.parent.parent / ".deepeval")


def _env(name: str, fallback: str = "") -> str:
    return os.environ.get(name, fallback)


def generation_config() -> dict:
    return {
        "base_url": _env("DEFAULT_GENERATION_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        "model": _env("DEFAULT_GENERATION_MODEL", "openai/gpt-oss-20b"),
        "api_key": _env("DEFAULT_GENERATION_API_KEY", ""),
    }


def evaluation_config() -> dict:
    return {
        "base_url": _env("DEFAULT_EVALUATION_BASE_URL", "https://integrate.api.nvidia.com/v1"),
        "model": _env("DEFAULT_EVALUATION_MODEL", "openai/gpt-oss-20b"),
        "api_key": _env("DEFAULT_EVALUATION_API_KEY", ""),
    }


def embedding_config() -> dict:
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


def build_rag_graph(gen_cfg: dict, emb_cfg: dict):
    """Compile the Agentic RAG graph from explicit provider configs."""
    llm = get_generation_llm(gen_cfg["base_url"], gen_cfg["model"], gen_cfg["api_key"])
    embeddings = get_embeddings(emb_cfg["base_url"], emb_cfg["model"], emb_cfg["api_key"])
    vector_store = ChromaStore(embeddings=embeddings)
    return build_agentic_rag_graph(llm, embeddings, vector_store)


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


def load_golden_dataset() -> List[dict]:
    """Load golden_dataset.json. Raises FileNotFoundError if missing."""
    if not GOLDEN_DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Golden dataset not found at {GOLDEN_DATASET_PATH}. "
            "Run `python -m tests.eval.generate_goldens` first."
        )
    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not data:
        raise ValueError("Golden dataset is empty.")
    return data


def _metric_to_dict(metric) -> dict:
    return {
        "name": metric.__class__.__name__,
        "score": round(float(metric.score), 4) if metric.score is not None else 0.0,
        "threshold": float(metric.threshold),
        "passed": bool(metric.is_successful()),
        "reason": metric.reason or "",
    }


def run_evals_streaming(
    gen_cfg: dict,
    eval_cfg: dict,
    emb_cfg: dict,
    progress_callback: Optional[Callable[[dict], None]] = None,
) -> dict:
    """Run end-to-end RAG evals over the golden dataset, emitting per-golden progress.

    Returns the aggregate EvalSummary dict on completion.
    """
    goldens = load_golden_dataset()
    graph = build_rag_graph(gen_cfg, emb_cfg)
    judge = NvidiaNimJudge(eval_cfg["base_url"], eval_cfg["model"], eval_cfg["api_key"])

    golden_results: List[dict] = []
    metric_accum: dict = {}

    for golden in goldens:
        question = golden["input"]
        expected = golden.get("expected_output", "")
        final_state = run_graph_for_question(graph, question)
        actual_output = final_state.get("generation", "")
        docs = final_state.get("documents", [])
        retrieval_context = [d["content"] for d in docs] if docs else []

        metrics = [
            AnswerRelevancyMetric(threshold=0.5, model=judge),
            FaithfulnessMetric(threshold=0.5, model=judge),
        ]
        if expected:
            metrics.append(ContextualPrecisionMetric(threshold=0.5, model=judge))
            metrics.append(ContextualRecallMetric(threshold=0.5, model=judge))

        test_case = LLMTestCase(
            input=question,
            expected_output=expected,
            actual_output=actual_output,
            retrieval_context=retrieval_context if retrieval_context else ["No context retrieved."],
        )

        for m in metrics:
            m.measure(test_case)

        metric_dicts = [_metric_to_dict(m) for m in metrics]
        golden_passed = all(md["passed"] for md in metric_dicts)
        result = {
            "input": question,
            "expected_output": expected,
            "actual_output": actual_output,
            "metrics": metric_dicts,
            "passed": golden_passed,
        }
        golden_results.append(result)

        for md in metric_dicts:
            name = md["name"]
            if name not in metric_accum:
                metric_accum[name] = {"scores": [], "passes": 0}
            metric_accum[name]["scores"].append(md["score"])
            if md["passed"]:
                metric_accum[name]["passes"] += 1

        if progress_callback:
            progress_callback(result)

    metric_averages = []
    for name, acc in metric_accum.items():
        scores = acc["scores"]
        metric_averages.append({
            "name": name,
            "avg_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "pass_rate": round(acc["passes"] / len(scores), 4) if scores else 0.0,
        })

    total = len(golden_results)
    passed = sum(1 for r in golden_results if r["passed"])
    summary = {
        "total": total,
        "passed": passed,
        "metric_averages": metric_averages,
        "goldens": golden_results,
        "run_at": datetime.now(timezone.utc).isoformat(),
    }

    _persist_summary(summary)
    return summary


def _persist_summary(summary: dict) -> None:
    """Write the summary as a timestamped JSON file in the results directory."""
    results_dir = Path(_env("DEEPEVAL_RESULTS_FOLDER", DEFAULT_RESULTS_DIR))
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = results_dir / f"eval_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


def load_latest_results() -> Optional[dict]:
    """Read the most recent eval_*.json from the results directory, or None."""
    results_dir = Path(_env("DEEPEVAL_RESULTS_FOLDER", DEFAULT_RESULTS_DIR))
    if not results_dir.exists():
        return None
    files = sorted(results_dir.glob("eval_*.json"), key=lambda p: p.name, reverse=True)
    if not files:
        return None
    with open(files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def generate_goldens_streaming(
    emb_cfg: dict,
    eval_cfg: dict,
    progress_callback: Optional[Callable[[dict], None]] = None,
) -> dict:
    """Synthesize ~20 goldens from the live Chroma store and write golden_dataset.json.

    Emits stage-level progress via progress_callback since the DeepEval
    Synthesizer does not emit per-golden progress callbacks.

    Returns {count, path} on completion. Raises on error (e.g. empty Chroma store).
    """
    if progress_callback:
        progress_callback({"stage": "reading_chroma", "message": "Reading chunks from Chroma store…"})

    from app.models.factory import get_embeddings
    from app.vectorstore.chroma_store import ChromaStore

    embeddings = get_embeddings(emb_cfg["base_url"], emb_cfg["model"], emb_cfg["api_key"])
    store = ChromaStore(embeddings=embeddings)
    collection = store._get_store()._collection
    results = collection.get(include=["documents"])
    docs = results.get("documents", [])
    if not docs:
        raise ValueError("Chroma store is empty. Ingest documents first (via the UI or API).")

    if progress_callback:
        progress_callback({"stage": "synthesizing", "message": f"Synthesizing goldens from {len(docs)} chunks (this may take a few minutes)…"})

    from deepeval.synthesizer import Synthesizer

    judge = NvidiaNimJudge(eval_cfg["base_url"], eval_cfg["model"], eval_cfg["api_key"])
    synthesizer = Synthesizer(model=judge, async_mode=False)
    synthesizer.generate_goldens_from_contexts(
        contexts=[[d] for d in docs],
        max_goldens_per_context=1,
    )

    goldens = []
    for golden in synthesizer.goldens:
        goldens.append({
            "input": golden.input,
            "expected_output": golden.expected_output,
            "expected_context": list(golden.context) if golden.context else [],
        })

    GOLDEN_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GOLDEN_DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(goldens, f, indent=2, ensure_ascii=False)

    if progress_callback:
        progress_callback({"stage": "done", "message": f"Wrote {len(goldens)} goldens."})

    return {"count": len(goldens), "path": str(GOLDEN_DATASET_PATH)}