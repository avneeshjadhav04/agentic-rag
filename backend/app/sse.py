"""Shared SSE streaming helpers used by the eval and ingestion endpoints.

Both long-running endpoints (eval runs and file ingestion) use the same
pattern: a blocking target function runs in a thread, emits progress via
a callback, and returns a final summary dict. This module bridges that
blocking call to an async SSE generator with a keepalive heartbeat.
"""
import asyncio
import json
from typing import AsyncGenerator, Callable

# SSE anti-buffering headers. Long-running endpoints emit events seconds
# or minutes apart; without these a PaaS reverse proxy (Railway, nginx,
# etc.) buffers the idle connection and the browser only sees the final
# `done` event after the socket closes. X-Accel-Buffering: no is the
# de-facto standard hint that switches such proxies to streaming/flush
# mode.
SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}

# Seconds between keepalive comments. Well under Railway's ~30s idle
# timeout — SSE comments (lines starting with ":") are ignored by the
# browser and our parser, but keep bytes flowing so the proxy doesn't
# kill the idle connection during long gaps between progress events.
HEARTBEAT_INTERVAL = 15


async def stream_threaded(
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
            try:
                item = await asyncio.wait_for(progress_queue.get(), timeout=HEARTBEAT_INTERVAL)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue
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