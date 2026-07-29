"""Thread-local trace buffer for live SSE streaming.

Both ``nodes.py`` and ``tools.py`` need to push trace events to the same
thread-local buffer so the chat endpoint can stream them via SSE.  This
module owns the buffer and the helpers that read/write it.
"""
import threading

_trace_buffers: dict[int, list[dict]] = {}
_trace_buffers_lock = threading.Lock()


def set_trace_buffer(buf: list[dict]) -> None:
    with _trace_buffers_lock:
        _trace_buffers[threading.get_ident()] = buf


def clear_trace_buffer() -> None:
    with _trace_buffers_lock:
        _trace_buffers.pop(threading.get_ident(), None)


def add_trace(state, step: str, detail: dict) -> None:
    """Append a trace entry to *state* (if not None) and push it to the live SSE buffer."""
    entry = {"step": step, **detail}
    if state is not None and "trace" in state:
        state["trace"].append(entry)
    with _trace_buffers_lock:
        buf = _trace_buffers.get(threading.get_ident())
    if buf is not None:
        buf.append(entry)