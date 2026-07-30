"""Context-var trace buffer for live SSE streaming.

Both ``nodes.py`` and ``tools.py`` need to push trace events to the same
buffer so the chat endpoint can stream them via SSE.

We use a ``contextvars.ContextVar`` instead of ``threading.get_ident()``
because ``create_agent``'s ``ToolNode`` executes tools in a
``ContextThreadPoolExecutor`` worker thread.  That executor copies the
calling context (``copy_context().run``) to each worker, so a contextvar
set in the ``asyncio.to_thread`` thread propagates through
``graph.invoke`` → ``ToolNode`` → tool wrappers — even across thread
boundaries.  A ``threading.get_ident()`` key would miss because the
worker thread has a different ID.
"""
import contextvars
from typing import Optional

_trace_buffer_var: contextvars.ContextVar[Optional[list[dict]]] = (
    contextvars.ContextVar("_trace_buffer_var", default=None)
)


def set_trace_buffer(buf: list[dict]) -> None:
    _trace_buffer_var.set(buf)


def clear_trace_buffer() -> None:
    _trace_buffer_var.set(None)


def add_trace(state, step: str, detail: dict) -> None:
    """Append a trace entry to *state* (if not None) and push it to the live SSE buffer."""
    entry = {"step": step, **detail}
    if state is not None and "trace" in state:
        state["trace"].append(entry)
    buf = _trace_buffer_var.get()
    if buf is not None:
        buf.append(entry)