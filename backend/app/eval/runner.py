"""Programmatic DeepEval RAG runner shared by the pytest harness and the live SSE endpoint.

This module owns the canonical implementations of:
  - NvidiaNimJudge (DeepEvalBaseLLM wrapping an OpenAI-compatible endpoint)
  - provider config helpers (generation / evaluation / embedding)
  - run_graph_for_question (invoke the Agentic RAG graph for one question)
  - run_evals_streaming (async generator; parallel goldens via asyncio + Semaphore)
  - generate_goldens_streaming (async generator; async_mode=True Synthesizer)
  - load_latest_results (read the most recent .deepeval/*.json from disk)
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

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
from app.agents.state import AgentState
from app.models.factory import get_embeddings, get_generation_llm
from app.vectorstore.chroma_store import ChromaStore

EVAL_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "eval"
GOLDEN_DATASET_PATH = EVAL_DIR / "golden_dataset.json"
DEFAULT_RESULTS_DIR = str(Path(__file__).resolve().parent.parent.parent / ".deepeval")

DEFAULT_EVAL_MAX_CONCURRENCY = 4


def _env(name: str, fallback: str = "") -> str:
    return os.environ.get(name, fallback)


def _env_int(name: str, fallback: int) -> int:
    try:
        return int(os.environ.get(name, str(fallback)))
    except (ValueError, TypeError):
        return fallback


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
        if not base_url or not model:
            raise ValueError("base_url and model are required")
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
    if not gen_cfg.get("base_url") or not gen_cfg.get("model"):
        raise ValueError("generation provider base_url and model are required")
    if not emb_cfg.get("base_url") or not emb_cfg.get("model"):
        raise ValueError("embedding provider base_url and model are required")
    llm = get_generation_llm(gen_cfg["base_url"], gen_cfg["model"], gen_cfg["api_key"])
    embeddings = get_embeddings(emb_cfg["base_url"], emb_cfg["model"], emb_cfg["api_key"])
    vector_store = ChromaStore(embeddings=embeddings)
    return build_agentic_rag_graph(llm, embeddings, vector_store)


def _initial_state(question: str) -> AgentState:
    return {
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


def run_graph_for_question(graph, question: str) -> dict:
    """Invoke the RAG graph for a single question and return the final state."""
    return graph.invoke(_initial_state(question))


async def run_graph_for_question_async(graph, question: str) -> dict:
    """Async-invoke the RAG graph for a single question and return the final state."""
    return await graph.ainvoke(_initial_state(question))


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


def _build_metrics(judge: NvidiaNimJudge, has_expected: bool) -> list:
    metrics = [
        AnswerRelevancyMetric(threshold=0.5, model=judge),
        FaithfulnessMetric(threshold=0.5, model=judge),
    ]
    if has_expected:
        metrics.append(ContextualPrecisionMetric(threshold=0.5, model=judge))
        metrics.append(ContextualRecallMetric(threshold=0.5, model=judge))
    return metrics


async def _score_one_golden(
    graph,
    judge: NvidiaNimJudge,
    golden: dict,
    idx: int,
    sem: asyncio.Semaphore,
) -> tuple[int, dict]:
    """Run the RAG graph + measure metrics for a single golden. Async safe.

    Returns (original_index, result_dict) so callers can re-sort into input order.
    Errors are caught so one failing golden doesn't abort the whole run; the
    failed golden gets passed=False with an "error" field instead.
    """
    question = golden["input"]
    expected = golden.get("expected_output", "")
    try:
        async with sem:
            final_state = await run_graph_for_question_async(graph, question)
        actual_output = final_state.get("generation", "") or ""
        docs = final_state.get("documents", [])
        retrieval_context = [d["content"] for d in docs] if docs else []

        test_case = LLMTestCase(
            input=question,
            expected_output=expected,
            actual_output=actual_output,
            retrieval_context=retrieval_context if retrieval_context else ["No context retrieved."],
        )

        metrics = _build_metrics(judge, bool(expected))
        for m in metrics:
            await m.a_measure(test_case)

        metric_dicts = [_metric_to_dict(m) for m in metrics]
        golden_passed = all(md["passed"] for md in metric_dicts)
        result = {
            "input": question,
            "expected_output": expected,
            "actual_output": actual_output,
            "metrics": metric_dicts,
            "passed": golden_passed,
        }
    except Exception as e:
        result = {
            "input": question,
            "expected_output": expected,
            "actual_output": "",
            "metrics": [],
            "passed": False,
            "error": str(e),
        }
    return idx, result


async def run_evals_streaming(
    gen_cfg: dict,
    eval_cfg: dict,
    emb_cfg: dict,
) -> AsyncGenerator[dict, None]:
    """Async generator: run RAG evals over the golden dataset in parallel.

    Yields {"type": "progress", "data": <golden_result>} as each golden completes,
    then {"type": "done", "data": <summary>} at the end, or {"type": "error", ...}.

    Concurrency is capped by EVAL_MAX_CONCURRENCY (env var, default 4).
    """
    if not eval_cfg.get("base_url") or not eval_cfg.get("model"):
        yield {"type": "error", "message": "evaluation provider base_url and model are required"}
        return
    if not gen_cfg.get("base_url") or not gen_cfg.get("model"):
        yield {"type": "error", "message": "generation provider base_url and model are required"}
        return
    if not emb_cfg.get("base_url") or not emb_cfg.get("model"):
        yield {"type": "error", "message": "embedding provider base_url and model are required"}
        return

    try:
        goldens = load_golden_dataset()
    except (FileNotFoundError, ValueError) as e:
        yield {"type": "error", "message": str(e)}
        return

    try:
        graph = build_rag_graph(gen_cfg, emb_cfg)
        judge = NvidiaNimJudge(eval_cfg["base_url"], eval_cfg["model"], eval_cfg["api_key"])
    except ValueError as e:
        yield {"type": "error", "message": str(e)}
        return

    max_concurrency = _env_int("EVAL_MAX_CONCURRENCY", DEFAULT_EVAL_MAX_CONCURRENCY)
    sem = asyncio.Semaphore(max_concurrency)

    tasks = [
        asyncio.create_task(_score_one_golden(graph, judge, g, i, sem))
        for i, g in enumerate(goldens)
    ]

    results_by_idx: Dict[int, dict] = {}
    metric_accum: dict = {}

    try:
        for coro in asyncio.as_completed(tasks):
            idx, result = await coro
            results_by_idx[idx] = result
            yield {"type": "progress", "data": result}

            for md in result.get("metrics", []):
                name = md["name"]
                if name not in metric_accum:
                    metric_accum[name] = {"scores": [], "passes": 0}
                metric_accum[name]["scores"].append(md["score"])
                if md["passed"]:
                    metric_accum[name]["passes"] += 1
    except (GeneratorExit, asyncio.CancelledError):
        for t in tasks:
            if not t.done():
                t.cancel()
        raise

    golden_results = [results_by_idx[i] for i in range(len(goldens))]

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
    yield {"type": "done", "data": summary}


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


async def generate_goldens_streaming(
    emb_cfg: dict,
    eval_cfg: dict,
) -> AsyncGenerator[dict, None]:
    """Async generator: synthesize goldens from the live Chroma store using async DeepEval.

    Uses Synthesizer(async_mode=True) + a_generate_goldens_from_contexts so all
    contexts are synthesized concurrently via DeepEval's internal asyncio.gather.

    Yields {"type": "progress", "data": {"stage":..., "message":...}} during work,
    then {"type": "done", "data": {"count":..., "path":...}} on completion.
    """
    for cfg_name, cfg in [("embedding", emb_cfg), ("evaluation", eval_cfg)]:
        if not cfg.get("base_url") or not cfg.get("model"):
            yield {
                "type": "error",
                "message": (
                    f"{cfg_name} provider base_url and model are required. "
                    f"Got base_url='{cfg.get('base_url', '')}', model='{cfg.get('model', '')}'. "
                    "Configure the evaluation and embedding providers in the sidebar."
                ),
            }
            return

    yield {"type": "progress", "data": {"stage": "reading_chroma", "message": "Reading chunks from Chroma store…"}}

    embeddings = get_embeddings(emb_cfg["base_url"], emb_cfg["model"], emb_cfg["api_key"])
    store = ChromaStore(embeddings=embeddings)
    collection = store._get_store()._collection
    results = collection.get(include=["documents"])
    docs = results.get("documents", [])
    if not docs:
        yield {"type": "error", "message": "Chroma store is empty. Ingest documents first (via the UI or API)."}
        return

    yield {
        "type": "progress",
        "data": {
            "stage": "synthesizing",
            "message": f"Synthesizing goldens from {len(docs)} chunks in parallel (this may take a minute)…",
        },
    }

    from deepeval.synthesizer import Synthesizer

    judge = NvidiaNimJudge(eval_cfg["base_url"], eval_cfg["model"], eval_cfg["api_key"])
    synthesizer = Synthesizer(model=judge, async_mode=True)
    try:
        generated = await synthesizer.a_generate_goldens_from_contexts(
            contexts=[[d] for d in docs],
            max_goldens_per_context=1,
        )
    except Exception as e:
        yield {"type": "error", "message": f"Synthesizer failed: {e}"}
        return

    # DeepEval 4.1.3 bug: a_generate_goldens_from_contexts() returns the goldens
    # list but does NOT assign it to self.synthetic_goldens (unlike the sync
    # version). Use the return value instead of synthesizer.synthetic_goldens.
    goldens = []
    for golden in generated:
        goldens.append({
            "input": golden.input,
            "expected_output": golden.expected_output,
            "expected_context": list(golden.context) if golden.context else [],
        })

    GOLDEN_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GOLDEN_DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(goldens, f, indent=2, ensure_ascii=False)

    yield {"type": "progress", "data": {"stage": "done", "message": f"Wrote {len(goldens)} goldens."}}
    yield {"type": "done", "data": {"count": len(goldens), "path": str(GOLDEN_DATASET_PATH)}}