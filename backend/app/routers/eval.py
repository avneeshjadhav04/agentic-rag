"""Evaluation endpoints for the Agentic RAG backend.

POST /api/eval/run              — SSE stream that runs DeepEval over the golden dataset,
                                  emitting per-golden progress + a final aggregate summary.
POST /api/eval/generate-goldens — SSE stream that synthesizes ~20 goldens from the live
                                  Chroma store, emitting stage progress + final count.
GET  /api/eval/results          — returns the latest on-disk eval result JSON.
"""
import asyncio
import json
from typing import AsyncGenerator, Callable

from fastapi import APIRouter, Form
from fastapi.responses import StreamingResponse

from app.eval.runner import generate_goldens_streaming, load_latest_results, run_evals_streaming

router = APIRouter(prefix="/api/eval", tags=["eval"])


async def _stream_threaded(
    target: Callable[[Callable[[dict], None]], dict],
) -> AsyncGenerator[str, None]:
    """Run a blocking target(gen) in a thread, bridging progress_callback to SSE events.

    target must accept a single progress_callback argument and return a dict summary.
    The generator emits SSE 'progress' events for each callback invocation, then a
    'done' event with the summary, or an 'error' event on failure.
    """
    progress_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def progress_callback(result: dict) -> None:
        loop.call_soon_threadsafe(progress_queue.put_nowait, result)

    def run_in_thread():
        try:
            summary = target(progress_callback)
            loop.call_soon_threadsafe(progress_queue.put_nowait, ("__done__", summary))
        except Exception as e:
            loop.call_soon_threadsafe(progress_queue.put_nowait, ("__error__", str(e)))

    task = asyncio.create_task(asyncio.to_thread(run_in_thread))

    try:
        while True:
            item = await progress_queue.get()
            if isinstance(item, tuple) and len(item) == 2:
                tag, payload = item
                if tag == "__done__":
                    yield f"event: done\ndata: {json.dumps(payload)}\n\n"
                    break
                if tag == "__error__":
                    yield f"event: error\ndata: {json.dumps({'message': payload})}\n\n"
                    break
            else:
                yield f"event: progress\ndata: {json.dumps(item)}\n\n"
    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"
    finally:
        if not task.done():
            task.cancel()


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

    def target(progress_callback: Callable[[dict], None]) -> dict:
        return run_evals_streaming(gen_cfg, eval_cfg, emb_cfg, progress_callback=progress_callback)

    return StreamingResponse(_stream_threaded(target), media_type="text/event-stream")


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

    def target(progress_callback: Callable[[dict], None]) -> dict:
        return generate_goldens_streaming(emb_cfg, eval_cfg, progress_callback=progress_callback)

    return StreamingResponse(_stream_threaded(target), media_type="text/event-stream")


@router.get("/results")
async def eval_results():
    results = load_latest_results()
    if results is None:
        return {"error": "No eval results found. Run evals first."}
    return results