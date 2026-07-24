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
import re
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

# Resolve everything relative to the backend root (the directory above this
# package's parent) so results land in the same place regardless of the CWD
# uvicorn / pytest / the CLI wrapper was launched from.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
EVAL_DIR = _BACKEND_ROOT / "tests" / "eval"
GOLDEN_DATASET_PATH = EVAL_DIR / "golden_dataset.json"
DEFAULT_RESULTS_DIR = str(_BACKEND_ROOT / ".deepeval")

# Maximum number of goldens to synthesize from the Chroma store, keeping
# golden generation and downstream evaluation bounded regardless of corpus size.
MAX_GOLDENS = 20


def _env(name: str, fallback: str = "") -> str:
    return os.environ.get(name, fallback)


def _resolve_results_dir() -> Path:
    """Resolve the results directory to an absolute path.

    - Unset env var -> the absolute <backend>/.deepeval default (resolved from
      this package's location, so it's correct regardless of the launch CWD).
    - Set env var -> honored literally: absolute paths used as-is, relative
      paths resolved against the process CWD (standard env-var semantics).
      See .env.example for the caveat when uvicorn is launched from backend/.

    This ensures the SSE/programmatic runner (which writes eval_*.json) and
    the `deepeval test run` CLI (which writes test_run_*.json via DeepEval
    itself) read/write the same directory regardless of the launch CWD.
    """
    folder = _env("DEEPEVAL_RESULTS_FOLDER", DEFAULT_RESULTS_DIR)
    return Path(folder).resolve()


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


def goldens_exist() -> bool:
    """True if golden_dataset.json exists on disk (goldens have been generated)."""
    return GOLDEN_DATASET_PATH.exists()


def list_goldens() -> List[dict]:
    """Return [{index, input, expected_output}] for each golden on disk, or [] if none."""
    if not GOLDEN_DATASET_PATH.exists():
        return []
    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [
        {"index": i, "input": g.get("input", ""), "expected_output": g.get("expected_output", "")}
        for i, g in enumerate(data)
    ]


def list_eval_runs() -> List[dict]:
    """List all eval/test_run JSONs (newest first) with lightweight metadata."""
    results_dir = _resolve_results_dir()
    if not results_dir.exists():
        return []
    out = []
    for p in _result_files(results_dir):
        ts = _TS_RE.search(p.stem)
        label = (
            datetime.strptime(ts.group(1), "%Y%m%dT%H%M%SZ").strftime("%Y-%m-%d %H:%M UTC")
            if ts else p.stem
        )
        total = passed = None
        try:
            with open(p, "r", encoding="utf-8") as f:
                d = json.load(f)
            if "testCases" in d:
                total = len(d.get("testCases", []))
                passed = int(d.get("testPassed", 0)) or sum(
                    1 for tc in d.get("testCases", []) if tc.get("success")
                )
            else:
                total = d.get("total")
                passed = d.get("passed")
        except (json.JSONDecodeError, OSError):
            pass
        out.append({"filename": p.name, "label": label, "total": total, "passed": passed})
    return out


def load_result_by_name(filename: str) -> Optional[dict]:
    """Load a single eval result file by filename, normalized to the SSE summary shape.

    Returns None if the file does not exist or the filename is unsafe (must end
    in .json and be a bare name, no path traversal).
    """
    if not filename.endswith(".json") or "/" in filename or "\\" in filename:
        return None
    p = _resolve_results_dir() / filename
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "testCases" in data:
        return _normalize_test_run(data)
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
            AnswerRelevancyMetric(threshold=0.5, model=judge, async_mode=False),
            FaithfulnessMetric(threshold=0.5, model=judge, async_mode=False),
        ]
        if expected:
            metrics.append(ContextualPrecisionMetric(threshold=0.5, model=judge, async_mode=False))
            metrics.append(ContextualRecallMetric(threshold=0.5, model=judge, async_mode=False))

        test_case = LLMTestCase(
            input=question,
            expected_output=expected,
            actual_output=actual_output,
            retrieval_context=retrieval_context,
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
    results_dir = _resolve_results_dir()
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = results_dir / f"eval_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)


_TS_RE = re.compile(r"(\d{8}T\d{6}Z)")


def _result_sort_key(p: Path) -> float:
    """Sort key (newest first) derived from the timestamp embedded in the name.

    Both writers use a UTC `%Y%m%dT%H%M%SZ` timestamp (eval_<ts>.json from this
    runner, test_run_<ts>.json from DeepEval CLI), so we sort by that rather
    than the raw filename — otherwise lexicographic order would rank
    `test_run_...` above `eval_...` regardless of when each was written.
    Files without a parseable timestamp fall back to the file's mtime.
    """
    m = _TS_RE.search(p.stem)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            pass
    return p.stat().st_mtime


def _result_files(results_dir: Path) -> List[Path]:
    """All eval result JSONs in the dir, newest first.

    Two writers produce results here:
      - this runner's SSE/programmatic path  -> eval_<ts>.json
      - `deepeval test run` (the CLI wrapper) -> test_run_<ts>.json
    Both are surfaced so the UI reflects whichever path produced the latest run.
    """
    return sorted(
        list(results_dir.glob("eval_*.json")) + list(results_dir.glob("test_run_*.json")),
        key=_result_sort_key,
        reverse=True,
    )


def _normalize_test_run(data: dict) -> dict:
    """Convert a DeepEval `test_run_*.json` into the SSE summary shape.

    DeepEval's CLI writes testCases + metricsScores with camelCase aliases;
    the SSE runner (and the frontend) expect {total, passed, metric_averages,
    goldens}. This normalizer bridges the two so load_latest_results always
    returns one shape regardless of which path produced the latest file.
    """
    goldens: List[dict] = []
    for tc in data.get("testCases", []) or []:
        metrics = []
        for md in tc.get("metricsData", []) or []:
            metrics.append({
                "name": md.get("name", ""),
                "score": round(float(md["score"]), 4) if md.get("score") is not None else 0.0,
                "threshold": float(md.get("threshold", 0.5)),
                "passed": bool(md.get("success", False)),
                "reason": md.get("reason", "") or "",
            })
        goldens.append({
            "input": tc.get("input", ""),
            "expected_output": tc.get("expectedOutput", ""),
            "actual_output": tc.get("actualOutput", ""),
            "metrics": metrics,
            "passed": bool(tc.get("success", False)) if metrics else True,
        })

    metric_averages: List[dict] = []
    for ms in data.get("metricsScores", []) or []:
        scores = ms.get("scores", []) or []
        passes = int(ms.get("passes", 0))
        n = len(scores) if scores else (passes + int(ms.get("fails", 0)))
        metric_averages.append({
            "name": ms.get("metric", ""),
            "avg_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
            "pass_rate": round(passes / n, 4) if n else 0.0,
        })

    total = len(goldens)
    passed = sum(1 for g in goldens if g["passed"])
    return {
        "total": total,
        "passed": passed,
        "metric_averages": metric_averages,
        "goldens": goldens,
        "run_at": datetime.now(timezone.utc).isoformat(),
        "source": "deepeval-cli",
    }


def load_latest_results() -> Optional[dict]:
    """Read the most recent result JSON from the results directory, or None.

    Covers both the SSE runner's `eval_*.json` (already in summary shape) and
    DeepEval CLI's `test_run_*.json` (normalized to the same shape). DeepEval
    CLI files are identified by the presence of a `testCases` key.
    """
    results_dir = _resolve_results_dir()
    if not results_dir.exists():
        return None
    files = _result_files(results_dir)
    if not files:
        return None
    with open(files[0], "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "testCases" in data:
        return _normalize_test_run(data)
    return data


def generate_goldens_streaming(
    emb_cfg: dict,
    eval_cfg: dict,
    progress_callback: Optional[Callable[[dict], None]] = None,
) -> dict:
    """Synthesize up to MAX_GOLDENS goldens from the live Chroma store.

    The store may contain hundreds of chunks; synthesizing one golden per
    chunk (and then running the full RAG graph + 4 LLM-judge metrics per
    golden in run_evals_streaming) scales linearly with corpus size. To keep
    generation and evaluation bounded, the chunks are deterministically
    sampled down to MAX_GOLDENS before synthesis.

    Emits stage-level progress via progress_callback since the DeepEval
    Synthesizer does not emit per-golden progress callbacks.

    Returns {count, path} on completion. Raises on error (e.g. empty Chroma store).
    """
    if progress_callback:
        progress_callback({"stage": "reading_chroma", "message": "Reading chunks from Chroma store…"})

    for cfg_name, cfg in [("embedding", emb_cfg), ("evaluation", eval_cfg)]:
        if not cfg.get("base_url") or not cfg.get("model"):
            raise ValueError(
                f"{cfg_name} provider base_url and model are required. "
                f"Got base_url='{cfg.get('base_url', '')}', model='{cfg.get('model', '')}'. "
                "Configure the evaluation and embedding providers in the sidebar."
            )

    from app.models.factory import get_embeddings
    from app.vectorstore.chroma_store import ChromaStore

    embeddings = get_embeddings(emb_cfg["base_url"], emb_cfg["model"], emb_cfg["api_key"])
    store = ChromaStore(embeddings=embeddings)
    collection = store._get_store()._collection
    results = collection.get(include=["documents"])
    docs = results.get("documents", [])
    if not docs:
        raise ValueError("Chroma store is empty. Ingest documents first (via the UI or API).")

    if len(docs) > MAX_GOLDENS:
        stride = len(docs) / MAX_GOLDENS
        docs = [docs[int(i * stride)] for i in range(MAX_GOLDENS)]

    if progress_callback:
        progress_callback({"stage": "synthesizing", "message": f"Synthesizing up to {len(docs)} goldens (this may take a few minutes)…"})

    from deepeval.synthesizer import Synthesizer

    judge = NvidiaNimJudge(eval_cfg["base_url"], eval_cfg["model"], eval_cfg["api_key"])
    # async_mode=False: generate_goldens_from_contexts() internally calls
    # loop.run_until_complete(...); under async_mode=True that requires
    # nest_asyncio patching of a running loop when this function is invoked
    # via asyncio.to_thread (the SSE path). The sync code path avoids that
    # fragility entirely while still producing the same goldens.
    synthesizer = Synthesizer(model=judge, async_mode=False)
    goldens_list = synthesizer.generate_goldens_from_contexts(
        contexts=[[d] for d in docs],
        max_goldens_per_context=1,
    )

    goldens = []
    for golden in goldens_list:
        goldens.append({
            "input": golden.input,
            "expected_output": golden.expected_output,
        })

    GOLDEN_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GOLDEN_DATASET_PATH, "w", encoding="utf-8") as f:
        json.dump(goldens, f, indent=2, ensure_ascii=False)

    if progress_callback:
        progress_callback({"stage": "done", "message": f"Wrote {len(goldens)} goldens."})

    return {"count": len(goldens), "path": str(GOLDEN_DATASET_PATH)}