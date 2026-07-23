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

from app.eval.runner import generate_goldens_streaming, goldens_exist, load_latest_results, run_evals_streaming

router = APIRouter(prefix="/api/eval", tags=["eval"])

# SSE anti-buffering headers. The eval endpoints emit one event per golden,
# minutes apart; without these a PaaS reverse proxy (Railway, nginx, etc.)
# buffers the idle connection and the browser only sees the final `done`
# event after the socket closes. X-Accel-Buffering: no is the de-facto
# standard hint that switches such proxies to streaming/flush mode.
SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


async def _stream_threaded(
    target: Callable[[Callable[[dict], None]], dict],
) -> AsyncGenerator[str, None]:
    """Run a blocking target(gen) in a thread, bridging progress_callback to SSE events.

    target must accept a single progress_callback argument and return a dict summary.
    The generator emits SSE 'progress' events for each callback invocation, then a
    'done' event with the summary, or an 'error' event on failure.

    On client disconnect the blocking thread cannot be force-cancelled (Python
    threads are not interruptible), so it runs to completion; but the callback
    becomes a no-op and the queue is drained in finally to avoid unbounded
    memory growth and needless work on a closed event loop.
    """
    progress_queue: asyncio.Queue = asyncio.Queue(maxsize=128)
    loop = asyncio.get_running_loop()
    client_gone = False

    def progress_callback(result: dict) -> None:
        if client_gone:
            return
        try:
            loop.call_soon_threadsafe(progress_queue.put_nowait, result)
        except RuntimeError:
            # Loop closed after disconnect — drop the progress event.
            pass

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
        client_gone = True
        if not task.done():
            task.cancel()
        # Drain any items the thread enqueued before noticing client_gone,
        # so they don't pile up after the generator returns.
        while not progress_queue.empty():
            try:
                progress_queue.get_nowait()
            except asyncio.QueueEmpty:
                break


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

    return StreamingResponse(_stream_threaded(target), media_type="text/event-stream", headers=SSE_HEADERS)


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

    return StreamingResponse(_stream_threaded(target), media_type="text/event-stream", headers=SSE_HEADERS)


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