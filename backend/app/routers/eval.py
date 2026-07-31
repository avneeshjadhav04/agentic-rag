"""Evaluation endpoints for the Agentic RAG backend.

POST /api/eval/run              — SSE stream that runs DeepEval over the golden dataset,
                                   emitting per-golden progress + a final aggregate summary.
POST /api/eval/generate-goldens — SSE stream that synthesizes goldens from the live
                                   Chroma store, emitting stage progress + final count.
                                   Optional max_goldens form field controls how many
                                   child chunks are fed to the Synthesizer (default 20).
GET  /api/eval/results          — returns the latest on-disk eval result JSON.
"""
from typing import Callable, Optional

from fastapi import APIRouter, Form
from fastapi.responses import StreamingResponse

from app.sse import SSE_HEADERS, stream_threaded

from app.eval.runner import (
    clear_eval_runs,
    clear_goldens,
    delete_eval_run,
    delete_golden,
    generate_goldens_streaming,
    get_golden_providers,
    goldens_exist,
    list_eval_runs,
    list_goldens,
    load_latest_results,
    load_result_by_name,
    run_evals_streaming,
)

router = APIRouter(prefix="/api/eval", tags=["eval"])


@router.post("/run")
async def eval_run(
    generation_provider: str = Form(default=""),
    generation_base_url: str = Form(...),
    generation_model: str = Form(...),
    generation_api_key: str = Form(default=""),
    evaluation_provider: str = Form(default=""),
    evaluation_base_url: str = Form(...),
    evaluation_model: str = Form(...),
    evaluation_api_key: str = Form(default=""),
    embed_provider: str = Form(default=""),
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
):
    gen_cfg = {"provider": generation_provider, "base_url": generation_base_url, "model": generation_model, "api_key": generation_api_key}
    eval_cfg = {"provider": evaluation_provider, "base_url": evaluation_base_url, "model": evaluation_model, "api_key": evaluation_api_key}
    emb_cfg = {"provider": embed_provider, "base_url": embed_base_url, "model": embed_model, "api_key": embed_api_key}

    def target(progress_callback: Callable[[dict], None]) -> dict:
        return run_evals_streaming(gen_cfg, eval_cfg, emb_cfg, progress_callback=progress_callback)

    return StreamingResponse(stream_threaded(target), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/generate-goldens")
async def eval_generate_goldens(
    evaluation_provider: str = Form(default=""),
    evaluation_base_url: str = Form(...),
    evaluation_model: str = Form(...),
    evaluation_api_key: str = Form(default=""),
    embed_provider: str = Form(default=""),
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
    max_goldens: Optional[int] = Form(default=None),
):
    eval_cfg = {"provider": evaluation_provider, "base_url": evaluation_base_url, "model": evaluation_model, "api_key": evaluation_api_key}
    emb_cfg = {"provider": embed_provider, "base_url": embed_base_url, "model": embed_model, "api_key": embed_api_key}

    def target(progress_callback: Callable[[dict], None]) -> dict:
        return generate_goldens_streaming(emb_cfg, eval_cfg, max_goldens=max_goldens, progress_callback=progress_callback)

    return StreamingResponse(stream_threaded(target), media_type="text/event-stream", headers=SSE_HEADERS)


@router.get("/results")
async def eval_results():
    results = load_latest_results()
    if results is None:
        return {"error": "No eval results found. Run evals first."}
    return results


@router.get("/goldens-exists")
async def eval_goldens_exists():
    """Whether golden_dataset.json exists on disk (goldens have been generated)."""
    return {"exists": goldens_exist()}


@router.get("/goldens-list")
async def eval_goldens_list():
    """List all goldens on disk with their input + expected_output for UI preview,
    along with the provider metadata captured at generation time."""
    return {"goldens": list_goldens(), "providers": get_golden_providers()}


@router.get("/runs-list")
async def eval_runs_list():
    """List all eval result files on disk (newest first) with lightweight metadata."""
    return {"runs": list_eval_runs()}


@router.get("/results/{filename}")
async def eval_result_by_name(filename: str):
    """Load a single eval result file by filename, normalized to the summary shape."""
    data = load_result_by_name(filename)
    if data is None:
        return {"error": f"No result file named '{filename}'."}
    return data


@router.delete("/goldens")
async def eval_clear_goldens():
    """Delete the entire golden_dataset.json file."""
    ok = clear_goldens()
    return {"ok": ok}


@router.delete("/goldens/{index}")
async def eval_delete_golden(index: int):
    """Remove a single golden by array index. Remaining goldens are reindexed."""
    ok = delete_golden(index)
    return {"ok": ok}


@router.delete("/runs")
async def eval_clear_runs():
    """Delete every eval_*.json and test_run_*.json in the results dir."""
    ok = clear_eval_runs()
    return {"ok": ok}


@router.delete("/runs/{filename}")
async def eval_delete_run(filename: str):
    """Delete a single eval result file by filename."""
    ok = delete_eval_run(filename)
    return {"ok": ok}