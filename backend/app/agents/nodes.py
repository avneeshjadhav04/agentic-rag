"""LangGraph nodes for the multi-agent RAG workflow.

Architecture: supervisor → researcher ↔ research_tools → supervisor
The supervisor uses with_structured_output for routing decisions. The
researcher uses bind_tools for native tool-calling (vector_search,
web_fetch, handoff). The writer synthesizes a grounded answer. The
quality_check critic uses with_structured_output to grade the answer.
"""
import re
import threading
from collections import Counter
from typing import Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.vectorstore.chroma_store import ChromaStore

from .state import AgentState
from .tools import _vector_search, _web_fetch

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


# ---------------------------------------------------------------------------
# Pydantic schemas for with_structured_output
# ---------------------------------------------------------------------------

class RouteDecision(BaseModel):
    next: Literal["researcher", "writer", "finish"] = Field(
        description="Which agent to call next"
    )
    reason: str = Field(description="Brief reasoning for the decision")


class QualityResult(BaseModel):
    grounded: bool = Field(description="Is the answer grounded in the context?")
    answers_question: bool = Field(description="Does the answer address the question?")
    feedback: str = Field(description="Feedback on the answer quality")


# ---------------------------------------------------------------------------
# Supervisor — main agent that decides which sub-agent to call next
# ---------------------------------------------------------------------------

def supervisor_node_factory(llm: ChatOpenAI):
    structured_llm = llm.with_structured_output(RouteDecision, method="function_calling")

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
        if state.get("tool_call_count", 0) > 0 and not has_docs:
            status_parts.append("The researcher has already run but found no relevant documents in the knowledge base.")
        researcher_summary = state.get("researcher_summary", "")
        if researcher_summary:
            status_parts.append(f"Researcher's last action: {researcher_summary}")
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
            "Guidelines:\n"
            "- If no documents have been gathered yet and the researcher has not run, "
            "call researcher.\n"
            "- If the researcher has already run but found no documents, call writer "
            "to state that the information is not available.\n"
            "- If documents have been gathered and no answer exists, call writer.\n"
            "- If the answer failed quality check due to missing information, call "
            "researcher to find better context.\n"
            "- If the answer failed quality check due to poor synthesis (not missing "
            "info), call writer to rewrite.\n"
            "- If max attempts are reached, call finish."
        )
        try:
            result = structured_llm.invoke(prompt)
            next_agent = result.next
            reason = result.reason
        except Exception:
            next_agent = "writer" if state.get("tool_call_count", 0) > 0 and not has_docs else ("researcher" if not has_docs else "writer")
            reason = "Fallback: unable to parse supervisor decision"

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
# Researcher — tool-calling agent using bind_tools
# ---------------------------------------------------------------------------

_MAX_TOOL_CALLS = 8


def researcher_node_factory(llm: ChatOpenAI, tools: list, max_tool_calls: int = _MAX_TOOL_CALLS):
    llm_with_tools = llm.bind_tools(tools, parallel_tool_calls=False)

    def researcher(state: AgentState) -> AgentState:
        question = state["question"]
        tool_call_count = state.get("tool_call_count", 0)
        feedback = state.get("quality_feedback", "")

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
            "Rules:\n"
            "- Always start by searching the local knowledge base with vector_search.\n"
            "- If the local results are insufficient, you may call web_fetch with a "
            "specific URL you are confident contains the answer.\n"
            "- You can call vector_search multiple times with different query phrasings "
            "to find different aspects of the question.\n"
            "- Do NOT repeat the same query — if a previous search returned irrelevant "
            "results, try a different query or use web_fetch instead.\n"
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

        response = llm_with_tools.invoke(messages)

        tool = "handoff"
        args: dict = {}
        tool_call_id: Optional[str] = None
        thought = response.content if hasattr(response, "content") else ""

        if response.tool_calls:
            tc = response.tool_calls[0]
            tool = tc["name"]
            args = tc["args"] or {}
            tool_call_id = tc["id"]
        else:
            thought = thought or "No tool call — handing off to supervisor."

        if force_handoff and tool != "handoff":
            tool = "handoff"
            args = {}
            tool_call_id = None
            thought = f"Reached max tool calls ({max_tool_calls}) — forcing handoff."

        if tool not in ("vector_search", "web_fetch", "handoff"):
            tool = "handoff"
            tool_call_id = None

        # Append the real AIMessage so the researcher sees its own tool call
        # on the next loop iteration.
        state["messages"] = state.get("messages", []) + [response]

        # Increment the researcher invocation counter here (not in
        # research_tools) so the force_handoff cap triggers even when the
        # researcher never calls a tool (e.g. it answers directly).
        state["tool_call_count"] = tool_call_count + 1

        # Build a concise summary for the supervisor — what the researcher
        # actually did and said, without the full document content.
        summary_parts = []
        if response.tool_calls:
            tc = response.tool_calls[0]
            summary_parts.append(f"Called {tc['name']} with args {tc['args']}")
        else:
            summary_parts.append("No tool called — handed off to supervisor")
        if thought:
            summary_parts.append(f"Reasoning: {thought}")
        state["researcher_summary"] = " | ".join(summary_parts)

        state["pending_tool"] = tool
        state["pending_args"] = args
        state["tool_call_id"] = tool_call_id
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
        tool_call_id = state.get("tool_call_id")

        # Dedup helper — prevents the same content from accumulating
        # in state["documents"] across repeated searches.
        existing_contents = {d["content"] for d in state["documents"]}

        if tool == "vector_search":
            query = args.get("query", question)
            result_text, docs = _vector_search(vector_store, k, query, llm, question)
            new_docs = [d for d in docs if d["content"] not in existing_contents]
            if new_docs:
                state["documents"].extend(new_docs)
            state["messages"] = state.get("messages", []) + [
                ToolMessage(content=result_text, tool_call_id=tool_call_id or ""),
            ]
            source_counts = Counter(
                (doc.get("metadata", {}).get("source_id", "unknown"),
                 doc.get("metadata", {}).get("source", "unknown"))
                for doc in new_docs
            )
            sources_summary = [
                {"source_id": sid, "source_name": name, "chunks": count}
                for (sid, name), count in source_counts.items()
            ]
            _add_trace(state, "tool_result", {
                "tool": "vector_search",
                "query": query,
                "new_docs": len(new_docs),
                "total_docs": len(state["documents"]),
                "sources": sources_summary,
            })

        elif tool == "web_fetch":
            url = args.get("url", "")
            result_text, docs = _web_fetch(url, question, llm)
            new_docs = [d for d in docs if d["content"] not in existing_contents]
            if new_docs:
                state["documents"].extend(new_docs)
            state["messages"] = state.get("messages", []) + [
                ToolMessage(content=result_text, tool_call_id=tool_call_id or ""),
            ]
            _add_trace(state, "tool_result", {
                "tool": "web_fetch",
                "url": url,
                "new_docs": len(new_docs),
                "total_docs": len(state["documents"]),
            })

        state["pending_tool"] = None
        state["pending_args"] = None
        state["tool_call_id"] = None
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
    structured_llm = llm.with_structured_output(QualityResult, method="function_calling")

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
            "evaluate whether the answer is grounded in the context and addresses the question.\n\n"
            f"Question: {question}\n\n"
            f"Answer: {generation}\n\n"
            f"Context:\n{context}"
        )
        try:
            result = structured_llm.invoke(prompt)
            grounded = result.grounded
            answers_question = result.answers_question
            feedback = result.feedback
        except Exception:
            grounded = True
            answers_question = True
            feedback = "Fallback: unable to parse quality check result"

        state["steps"] += 1
        state["quality_passed"] = grounded and answers_question
        if not state["quality_passed"] and state["steps"] < state.get("max_loops", 3):
            state["quality_feedback"] = feedback
            state["tool_call_count"] = 0
            state["researcher_summary"] = None
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