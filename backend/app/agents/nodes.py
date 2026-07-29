"""Nodes for the multi-agent RAG workflow (subagents pattern).

Architecture:
    START → main_agent ↔ (research, draft_answer, finalize_answer tools)
                      ↓
               prepare_generation (extracts answer if finalize wasn't called)
                      ↓
               quality_check (deterministic node)
                      ↓
              pass / max_loops → END
              fail + retries   → QualityFeedbackMessage → main_agent (retry)
"""
from typing import Annotated

from langchain.agents import create_agent
from langchain.messages import ToolMessage
from langchain.tools import InjectedToolCallId, tool
from langchain_openai import ChatOpenAI
from langgraph.types import Command
from pydantic import BaseModel, Field

from app.vectorstore.chroma_store import ChromaStore

from .state import WorkflowState
from .tools import build_research_tools
from .trace import add_trace, set_trace_buffer, clear_trace_buffer

# Module-level reference to the outer WorkflowState, set before graph.invoke()
# and cleared after. create_agent does not inject ToolRuntime, so tool wrappers
# use this to access the real state for trace appending and stop_event checks.
_current_state: WorkflowState | None = None


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class QualityResult(BaseModel):
    grounded: bool = Field(description="Is the answer grounded in the context?")
    answers_question: bool = Field(description="Does the answer address the question?")
    feedback: str = Field(description="Feedback on the answer quality")


# ---------------------------------------------------------------------------
# QualityFeedbackMessage — system-level feedback injected after a failed
# quality check. Subclasses SystemMessage so the LLM sees it as a system
# directive, not a user turn or another agent's claim.
# ---------------------------------------------------------------------------

from langchain_core.messages import SystemMessage


class QualityFeedbackMessage(SystemMessage):
    """Feedback from the quality check step, injected as system context."""

    def __init__(self, content: str, **kwargs):
        super().__init__(content=content, **kwargs)


# ---------------------------------------------------------------------------
# Main agent — create_agent with research, draft_answer, finalize_answer tools
# ---------------------------------------------------------------------------

def main_agent_factory(
    llm: ChatOpenAI,
    vector_store: ChromaStore,
    k: int = 4,
    web_search_enabled: bool = False,
):
    """Build the main agent (supervisor) using create_agent + subagent tools.

    The main agent has three tools:
      - research: wraps a research subagent (create_agent with vector_search/web_fetch)
      - draft_answer: wraps a writer subagent (create_agent, generation only)
      - finalize_answer: writes the final answer to state["generation"]

    Returns a compiled CompiledStateGraph suitable for use as a node in the
    outer workflow graph.
    """
    # --- Research subagent ------------------------------------------------
    research_tools = build_research_tools(vector_store, k, llm, web_search_enabled)

    research_agent = create_agent(
        model=llm,
        tools=research_tools,
        system_prompt=(
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
            "- When you have gathered enough context, respond with a concise summary "
            "of your findings.\n"
            "- If the local knowledge base is empty or has no relevant results after "
            "reasonable effort, state that information is unavailable."
        ),
        state_schema=WorkflowState,
    )

    # --- Writer subagent (no tools, generation only) ----------------------
    writer_agent = create_agent(
        model=llm,
        tools=[],
        system_prompt=(
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
            "not infer, correct, or alter them."
        ),
    )

    # --- Tool wrappers ----------------------------------------------------

    @tool("research", description=(
        "Research a question by searching the local knowledge base and optionally "
        "fetching web pages. Returns a summary of relevant findings."
    ))
    def call_research(
        query: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        """Delegate research to the research subagent."""
        global _current_state
        state = _current_state
        if state is None:
            return Command(update={
                "messages": [ToolMessage(content="[No state]", tool_call_id=tool_call_id)],
            })
        stop_event = state.get("stop_event")
        if stop_event and stop_event.is_set():
            return Command(update={
                "messages": [ToolMessage(content="[Stopped]", tool_call_id=tool_call_id)],
            })

        add_trace(state, "research", {"query": query})

        real_question = state.get("question", query)
        import app.agents.tools as tools_mod
        tools_mod._current_state = state
        try:
            result = research_agent.invoke({
                "messages": [{"role": "user", "content": (
                    f"User's question: {real_question}\n\n"
                    f"Suggested search query: {query}"
                )}],
                "documents": state.get("documents", []),
                "trace": state.get("trace", []),
                "question": real_question,
                "stop_event": state.get("stop_event"),
            })
        finally:
            tools_mod._current_state = None
        findings = result["messages"][-1].content
        subagent_docs = result.get("documents", [])
        subagent_trace = result.get("trace", [])

        add_trace(state, "research_result", {
            "findings_length": len(findings) if findings else 0,
            "total_docs": len(subagent_docs),
        })

        return Command(update={
            "documents": subagent_docs,
            "trace": state.get("trace", []) + subagent_trace,
            "messages": [ToolMessage(content=findings, tool_call_id=tool_call_id)],
        })

    @tool("draft_answer", description=(
        "Draft an answer from the research findings and context. Pass the question "
        "and any research findings as the query. Returns a draft answer."
    ))
    def call_draft(
        query: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> Command:
        """Delegate drafting to the writer subagent."""
        global _current_state
        state = _current_state
        if state is None:
            return Command(update={
                "messages": [ToolMessage(content="[No state]", tool_call_id=tool_call_id)],
            })
        stop_event = state.get("stop_event")
        if stop_event and stop_event.is_set():
            return Command(update={
                "messages": [ToolMessage(content="[Stopped]", tool_call_id=tool_call_id)],
            })

        add_trace(state, "draft", {"query_length": len(query)})

        real_question = state.get("question", "")
        draft_input = f"User's question: {real_question}\n\n{query}" if real_question else query
        result = writer_agent.invoke({
            "messages": [{"role": "user", "content": draft_input}],
        })
        draft = result["messages"][-1].content

        add_trace(state, "draft_result", {
            "draft_length": len(draft) if draft else 0,
        })

        return Command(update={
            "messages": [ToolMessage(content=draft, tool_call_id=tool_call_id)],
            "trace": state.get("trace", []),
        })

    # --- Main agent (supervisor) ------------------------------------------
    main_agent = create_agent(
        model=llm,
        tools=[call_research, call_draft],
        system_prompt=(
            "You are the main agent of a multi-agent RAG system. You coordinate "
            "specialized subagents and produce the final answer.\n\n"
            "Workflow:\n"
            "1. Call the `research` tool with the user's EXACT question — pass it "
            "verbatim, do not reformulate, paraphrase, or simplify it.\n"
            "2. Call the `draft_answer` tool with the question and research findings to "
            "get a draft answer.\n"
            "3. Review the draft and respond with your final, polished answer as plain "
            "text — do NOT call any tools for the final answer.\n\n"
            "If you receive quality feedback (a system message about issues), address "
            "the feedback by researching more thoroughly and producing a better answer.\n\n"
            "Rules:\n"
            "- Always research before drafting.\n"
            "- Your final answer must be grounded in the research findings.\n"
            "- If research returns no relevant documents, state that the information "
            "is not available in the final answer."
        ),
        state_schema=WorkflowState,
    )

    def wrapped_main_agent(state: WorkflowState) -> dict:
        """Set _current_state before invoking the subgraph, clear after."""
        global _current_state
        _current_state = state
        try:
            return main_agent.invoke(state)
        finally:
            _current_state = None

    return wrapped_main_agent


# ---------------------------------------------------------------------------
# Prepare generation — ensures state["generation"] is set before quality check
# ---------------------------------------------------------------------------

def prepare_generation_node(state: WorkflowState) -> dict:
    """If finalize_answer wasn't called, extract generation from the last AIMessage."""
    if state.get("generation"):
        return {}
    messages = state.get("messages", [])
    if messages:
        last = messages[-1]
        if hasattr(last, "content") and not getattr(last, "tool_calls", None):
            return {"generation": last.content}
    return {}


# ---------------------------------------------------------------------------
# Quality check — deterministic node, always runs LLM
# ---------------------------------------------------------------------------

def quality_check_node_factory(llm: ChatOpenAI):
    structured_llm = llm.with_structured_output(QualityResult, method="function_calling")

    def quality_check(state: WorkflowState) -> dict:
        """Grade state["generation"] against state["documents"].

        Always runs the LLM — no short-circuit on empty docs. On failure
        with retries remaining, appends a QualityFeedbackMessage to messages
        so the main agent sees the feedback on its next turn.
        """
        docs = state["documents"]
        question = state.get("question", "")

        generation = state.get("generation", "")
        context = "\n\n---\n\n".join(d["content"] for d in docs) if docs else "(no documents retrieved)"

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

        state["steps"] = state.get("steps", 0) + 1
        passed = grounded and answers_question
        state["quality_passed"] = passed

        updates: dict = {
            "steps": state["steps"],
            "quality_passed": passed,
        }

        if not passed and state["steps"] < state.get("max_loops", 3):
            state["quality_feedback"] = feedback
            updates["quality_feedback"] = feedback
            updates["messages"] = [
                QualityFeedbackMessage(
                    content=(
                        f"Quality check failed (attempt {state['steps']}). "
                        f"Feedback: {feedback}\n\n"
                        "Please address these issues: research more thoroughly, "
                        "draft a better answer, and call finalize_answer again."
                    )
                )
            ]
        else:
            state["quality_feedback"] = None
            updates["quality_feedback"] = None

        add_trace(state, "quality_check", {
            "grounded": grounded,
            "answers_question": answers_question,
            "feedback": feedback,
            "attempt": state["steps"],
        })

        return updates

    return quality_check


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def route_after_main(state: WorkflowState) -> str:
    """Always go to prepare_generation (which feeds into quality_check)."""
    return "prepare_generation"


def route_after_prepare(state: WorkflowState) -> str:
    """Route to quality_check if generation is set, otherwise end."""
    if state.get("generation"):
        return "quality_check"
    return "end"


def route_after_quality(state: WorkflowState) -> str:
    """Route to END on pass or max_loops, else back to main_agent."""
    if state.get("quality_passed") or state.get("steps", 0) >= state.get("max_loops", 3):
        return "end"
    return "main_agent"