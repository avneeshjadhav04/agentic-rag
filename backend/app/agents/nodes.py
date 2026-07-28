"""LangGraph nodes for the multi-agent RAG workflow.

Architecture: supervisor → researcher ↔ research_tools → writer → quality_check
The supervisor is an LLM that decides which sub-agent to call next. The
researcher is a tool-calling ReAct agent (vector_search, web_fetch, handoff).
The writer synthesizes a grounded answer from gathered context. The
quality_check critic grades the answer and routes feedback back to the
supervisor on failure.
"""
import json
import re
import threading
from collections import Counter
from typing import Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI

from app.vectorstore.chroma_store import ChromaStore

from .state import AgentState
from .tools import (
    VECTOR_SEARCH_DESC,
    WEB_FETCH_DESC,
    HANDOFF_DESC,
    vector_search as _vector_search,
    web_fetch as _web_fetch,
)

_trace_buffers: dict[int, list[dict]] = {}
_trace_buffers_lock = threading.Lock()


def set_trace_buffer(buf: list[dict]) -> None:
    with _trace_buffers_lock:
        _trace_buffers[threading.get_ident()] = buf


def clear_trace_buffer() -> None:
    with _trace_buffers_lock:
        _trace_buffers.pop(threading.get_ident(), None)


def _add_trace(state: AgentState, step: str, detail: dict) -> None:
    entry = {"step": step, **detail}
    state["trace"].append(entry)
    with _trace_buffers_lock:
        buf = _trace_buffers.get(threading.get_ident())
    if buf is not None:
        buf.append(entry)


def _llm_json_invoke(llm: ChatOpenAI, prompt: str, fallback: dict) -> dict:
    try:
        response = llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        else:
            obj_match = re.search(r"\{.*\}", text, re.DOTALL)
            if obj_match:
                text = obj_match.group(0)
        return json.loads(text.strip())
    except Exception:
        return fallback


# ---------------------------------------------------------------------------
# Supervisor — main agent that decides which sub-agent to call next
# ---------------------------------------------------------------------------

def supervisor_node_factory(llm: ChatOpenAI):
    def supervisor(state: AgentState) -> AgentState:
        question = state["question"]
        has_docs = bool(state["documents"])
        has_generation = bool(state.get("generation"))
        feedback = state.get("quality_feedback", "")
        steps = state.get("steps", 0)

        status_parts = []
        if has_docs:
            doc_sources = [
                doc.get("metadata", {}).get("source", "unknown")
                for doc in state["documents"]
            ]
            status_parts.append(f"Documents gathered: {len(state['documents'])} from {doc_sources}")
        else:
            status_parts.append("No documents gathered yet.")
        if has_generation:
            status_parts.append("An answer has been generated but failed quality check.")
        if feedback:
            status_parts.append(f"Quality check feedback: {feedback}")
        status = "\n".join(status_parts)

        prompt = (
            "You are the supervisor of a multi-agent RAG system. You decide which "
            "sub-agent should act next based on the current state.\n\n"
            "Available agents:\n"
            "- researcher: Searches the local knowledge base and fetches web pages "
            "to gather relevant context. Call this when you need more information.\n"
            "- writer: Synthesizes a grounded answer from gathered context. Call "
            "this when sufficient documents have been gathered.\n"
            "- finish: The task is complete (answer passed quality check or max "
            "attempts reached). Call this to end.\n\n"
            f"Current status:\n{status}\n\n"
            f"User question: {question}\n\n"
            f"Quality check attempts so far: {steps}\n\n"
            "Respond with ONLY a JSON object — no text before or after: "
            '{"next": "researcher" | "writer" | "finish", "reason": "..."}\n\n'
            "Guidelines:\n"
            "- If no documents have been gathered yet, call researcher.\n"
            "- If documents have been gathered and no answer exists, call writer.\n"
            "- If the answer failed quality check due to missing information, call "
            "researcher to find better context.\n"
            "- If the answer failed quality check due to poor synthesis (not missing "
            "info), call writer to rewrite.\n"
            "- If max attempts are reached, call finish.\n"
            "JSON:"
        )
        result = _llm_json_invoke(llm, prompt, {"next": "researcher", "reason": ""})
        next_agent = result.get("next", "researcher")
        if next_agent not in ("researcher", "writer", "finish"):
            next_agent = "researcher" if not has_docs else "writer"
        reason = result.get("reason", "")
        state["next_agent"] = next_agent
        _add_trace(state, "supervisor", {"next": next_agent, "reason": reason})
        return state

    return supervisor


def route_after_supervisor(state: AgentState) -> str:
    next_agent = state.get("next_agent", "researcher")
    if next_agent == "finish":
        return "end"
    return next_agent


# ---------------------------------------------------------------------------
# Researcher — tool-calling ReAct agent for information gathering
# ---------------------------------------------------------------------------

_MAX_TOOL_CALLS = 8


def researcher_node_factory(llm: ChatOpenAI, allow_web_fetch: bool, max_tool_calls: int = _MAX_TOOL_CALLS):
    def researcher(state: AgentState) -> AgentState:
        question = state["question"]
        tool_call_count = state.get("tool_call_count", 0)
        feedback = state.get("quality_feedback", "")

        tool_descriptions = [VECTOR_SEARCH_DESC, HANDOFF_DESC]
        if allow_web_fetch:
            tool_descriptions.append(WEB_FETCH_DESC)
        tools_text = "\n\n".join(tool_descriptions)

        feedback_text = ""
        if feedback and tool_call_count == 0:
            feedback_text = (
                f"\n\nNote: A previous attempt failed quality check with this "
                f"feedback: {feedback}\nPlease research more thoroughly to address "
                f"these issues."
            )

        system_content = (
            "You are a research agent in a multi-agent RAG system. Your job is to "
            "gather relevant information to answer the user's question.\n\n"
            f"Available tools:\n\n{tools_text}\n\n"
            "Respond with ONLY a JSON object — no text before or after:\n"
            '  {"tool": "<tool_name>", "args": {...}, "thought": "brief reasoning"}\n\n'
            "Rules:\n"
            "- Always start by searching the local knowledge base with vector_search.\n"
            "- If the local results are insufficient, you may call web_fetch with a "
            "specific URL you are confident contains the answer.\n"
            "- You can call vector_search multiple times with different query phrasings "
            "to find different aspects of the question.\n"
            "- When you have gathered enough context, call handoff to pass control back "
            "to the supervisor.\n"
            "- If the local knowledge base is empty or has no relevant results after "
            "reasonable effort, call handoff so the writer can state that information "
            "is unavailable."
            f"{feedback_text}"
        )

        messages = [
            SystemMessage(content=system_content),
            *state["messages"],
            HumanMessage(content=question),
        ]

        force_handoff = tool_call_count >= max_tool_calls
        if force_handoff:
            messages.append(HumanMessage(content=(
                f"You have reached the maximum of {max_tool_calls} tool calls. "
                "You must now call handoff to pass control to the supervisor."
            )))

        response = llm.invoke(messages)
        text = response.content if hasattr(response, "content") else str(response)

        match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            text = match.group(1)
        else:
            obj_match = re.search(r"\{.*\}", text, re.DOTALL)
            if obj_match:
                text = obj_match.group(0)

        try:
            result = json.loads(text.strip())
            tool = result.get("tool", "handoff")
            args = result.get("args", {}) or {}
            thought = result.get("thought", "")
        except (json.JSONDecodeError, AttributeError):
            tool = "handoff"
            args = {}
            thought = "Unable to parse response — handing off to supervisor."

        if force_handoff and tool != "handoff":
            tool = "handoff"
            args = {}
            thought = f"Reached max tool calls ({max_tool_calls}) — forcing handoff."

        if tool not in ("vector_search", "web_fetch", "handoff"):
            tool = "handoff"
        if tool == "web_fetch" and not allow_web_fetch:
            tool = "handoff"
            thought = "Web fetch is disabled — handing off to supervisor."

        state["pending_tool"] = tool
        state["pending_args"] = args
        _add_trace(state, "researcher", {
            "thought": thought,
            "tool": tool,
            "args": args,
            "tool_call_count": tool_call_count,
        })
        return state

    return researcher


def route_after_researcher(state: AgentState) -> str:
    pending = state.get("pending_tool")
    if pending in ("vector_search", "web_fetch"):
        return "research_tools"
    return "supervisor"


# ---------------------------------------------------------------------------
# Research tools — executes the pending tool call from the researcher
# ---------------------------------------------------------------------------

def research_tools_node_factory(vector_store: ChromaStore, llm: ChatOpenAI, k: int = 4):
    def research_tools(state: AgentState) -> AgentState:
        tool = state.get("pending_tool")
        args = state.get("pending_args", {}) or {}
        question = state["question"]

        if tool == "vector_search":
            query = args.get("query", question)
            result_text, docs = _vector_search(vector_store, k, query)
            if docs:
                state["documents"].extend(docs)
            state["messages"] = state.get("messages", []) + [
                AIMessage(content=f'[vector_search query="{query}"]'),
                ToolMessage(content=result_text, tool_call_id=f"vs_{state.get('tool_call_count', 0)}"),
            ]
            source_counts = Counter(
                (doc.get("metadata", {}).get("source_id", "unknown"),
                 doc.get("metadata", {}).get("source", "unknown"))
                for doc in docs
            )
            sources_summary = [
                {"source_id": sid, "source_name": name, "chunks": count}
                for (sid, name), count in source_counts.items()
            ]
            _add_trace(state, "tool_result", {
                "tool": "vector_search",
                "query": query,
                "new_docs": len(docs),
                "total_docs": len(state["documents"]),
                "sources": sources_summary,
            })

        elif tool == "web_fetch":
            url = args.get("url", "")
            result_text, docs = _web_fetch(url, question, llm)
            if docs:
                state["documents"].extend(docs)
            state["messages"] = state.get("messages", []) + [
                AIMessage(content=f'[web_fetch url="{url}"]'),
                ToolMessage(content=result_text, tool_call_id=f"wf_{state.get('tool_call_count', 0)}"),
            ]
            _add_trace(state, "tool_result", {
                "tool": "web_fetch",
                "url": url,
                "new_docs": len(docs),
                "total_docs": len(state["documents"]),
            })

        state["tool_call_count"] = state.get("tool_call_count", 0) + 1
        state["pending_tool"] = None
        state["pending_args"] = None
        return state

    return research_tools


# ---------------------------------------------------------------------------
# Writer — generation agent that synthesizes a grounded answer
# ---------------------------------------------------------------------------

def writer_node_factory(llm: ChatOpenAI):
    def writer(state: AgentState) -> AgentState:
        question = state["question"]
        docs = state["documents"]
        if docs:
            context_parts = []
            for i, doc in enumerate(docs):
                source = doc.get("metadata", {}).get("source", f"doc {i + 1}")
                context_parts.append(f"Source: {source}\n{doc['content']}")
            context = "\n\n---\n\n".join(context_parts)
        else:
            context = "No relevant context found."
        llm_messages = [
            SystemMessage(content=(
                "You are a helpful assistant. Use only the provided context to answer the "
                "user's question. If the context does not contain enough information, say so. "
                "Use markdown formatting only. Do not use HTML tags. For line breaks, "
                "end the line with two spaces or use a blank line between paragraphs.\n\n"
                "Follow these rules strictly:\n"
                "- Answer the parts the context supports first. Only state what is missing "
                "for the remainder, and only if it is genuinely absent.\n"
                "- Answer exactly what was asked. Omit adjacent facts (other projects, "
                "certifications, or purposes) that were not requested.\n"
                "- Copy names, dates, and statuses verbatim as written in the context; do "
                "not infer, correct, or alter them.\n\n"
                f"Context:\n{context}"
            )),
            *state["messages"],
            HumanMessage(content=question),
        ]
        response = llm.invoke(llm_messages)
        generation = response.content if hasattr(response, "content") else str(response)
        generation = re.sub(r"<br\s*/?>", "\n\n", generation, flags=re.IGNORECASE)
        state["generation"] = generation
        source_counts = Counter(
            (doc.get("metadata", {}).get("source_id", "unknown"),
             doc.get("metadata", {}).get("source", "unknown"))
            for doc in docs
        )
        sources_used = [
            {"source_id": sid, "source_name": name, "chunks": count}
            for (sid, name), count in source_counts.items()
        ]
        _add_trace(state, "writer", {
            "has_context": bool(docs),
            "length": len(generation),
            "sources_used": sources_used,
        })
        return state

    return writer


# ---------------------------------------------------------------------------
# Quality check — critic that grades the writer's answer
# ---------------------------------------------------------------------------

def quality_check_node_factory(llm: ChatOpenAI):
    def quality_check(state: AgentState) -> AgentState:
        docs = state["documents"]
        if not docs:
            state["steps"] += 1
            state["quality_passed"] = True
            state["quality_feedback"] = None
            _add_trace(
                state,
                "quality_check",
                {
                    "grounded": True,
                    "answers_question": True,
                    "feedback": "No context available \u2014 answer correctly states it lacks information.",
                    "attempt": state["steps"],
                },
            )
            return state
        question = state["question"]
        generation = state.get("generation", "")
        context = "\n\n---\n\n".join(d["content"] for d in docs) if docs else ""
        prompt = (
            "You are a quality checker. Given a question, an answer, and supporting context, "
            "Respond with ONLY a JSON object — no text before or after: "
            "{\"grounded\": true/false, \"answers_question\": true/false, \"feedback\": \"...\"}\n\n"
            f"Question: {question}\n\n"
            f"Answer: {generation}\n\n"
            f"Context:\n{context}\n\n"
            "JSON:"
        )
        result = _llm_json_invoke(llm, prompt, {"grounded": True, "answers_question": True})
        grounded = bool(result.get("grounded"))
        answers_question = bool(result.get("answers_question"))
        feedback = result.get("feedback", "")
        state["steps"] += 1
        state["quality_passed"] = grounded and answers_question
        if not state["quality_passed"] and state["steps"] < state.get("max_loops", 3):
            state["quality_feedback"] = feedback
            state["tool_call_count"] = 0
        else:
            state["quality_feedback"] = None
        _add_trace(
            state,
            "quality_check",
            {
                "grounded": grounded,
                "answers_question": answers_question,
                "feedback": feedback,
                "attempt": state["steps"],
            },
        )
        return state

    return quality_check


def route_after_quality(state: AgentState) -> str:
    if state["quality_passed"]:
        return "end"
    if state["steps"] >= state.get("max_loops", 3):
        return "end"
    return "supervisor"