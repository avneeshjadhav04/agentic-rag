"""Evaluation endpoints for the Agentic RAG backend.

POST /api/eval/run              — SSE stream that runs DeepEval over the golden dataset,
                                  emitting per-golden progress + a final aggregate summary.
POST /api/eval/generate-goldens — SSE stream that synthesizes goldens from the live
                                  Chroma store, emitting stage progress + final count.
GET  /api/eval/results          — returns the latest on-disk eval result JSON.
"""
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Form
from fastapi.responses import StreamingResponse

from app.eval.runner import generate_goldens_streaming, load_latest_results, run_evals_streaming

router = APIRouter(prefix="/api/eval", tags=["eval"])


async def _stream_async(
    source: AsyncGenerator[dict, None],
) -> AsyncGenerator[str, None]:
    """Bridge an async generator of {"type": ...} dicts into SSE events.

    Emits SSE 'progress' events for each progress dict, a 'done' event with the
    final summary, or an 'error' event on failure.
    """
    try:
        async for event in source:
            etype = event.get("type")
            if etype == "progress":
                yield f"event: progress\ndata: {json.dumps(event['data'])}\n\n"
            elif etype == "done":
                yield f"event: done\ndata: {json.dumps(event['data'])}\n\n"
                break
            elif etype == "error":
                yield f"event: error\ndata: {json.dumps({'message': event.get('message', '')})}\n\n"
                break
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"


@router.post("/run")
async def eval_run(
    generation_base_url: str = Form(...),
    generation_model: str = Form(...),
    generation_api_key: str = Form(default=""),
    evaluation_base_url: str = Form(...),
    evaluation_model: str = Form(...),
    evaluation_api_key: str = Form(default=""),
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
):
    gen_cfg = {"base_url": generation_base_url, "model": generation_model, "api_key": generation_api_key}
    eval_cfg = {"base_url": evaluation_base_url, "model": evaluation_model, "api_key": evaluation_api_key}
    emb_cfg = {"base_url": embed_base_url, "model": embed_model, "api_key": embed_api_key}

    return StreamingResponse(
        _stream_async(run_evals_streaming(gen_cfg, eval_cfg, emb_cfg)),
        media_type="text/event-stream",
    )


@router.post("/generate-goldens")
async def eval_generate_goldens(
    evaluation_base_url: str = Form(...),
    evaluation_model: str = Form(...),
    evaluation_api_key: str = Form(default=""),
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
):
    eval_cfg = {"base_url": evaluation_base_url, "model": evaluation_model, "api_key": evaluation_api_key}
    emb_cfg = {"base_url": embed_base_url, "model": embed_model, "api_key": embed_api_key}

    return StreamingResponse(
        _stream_async(generate_goldens_streaming(emb_cfg, eval_cfg)),
        media_type="text/event-stream",
    )


@router.get("/results")
async def eval_results():
    results = load_latest_results()
    if results is None:
        return {"error": "No eval results found. Run evals first."}
    return results