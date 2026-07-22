"""Component-level RAG evaluation with DeepEval + LangGraph callbacks.

Wraps the LangGraph invocation with DeepEval's CallbackHandler to produce
per-span traces, then scores:
  - the `generate` node's LLM span with AnswerRelevancyMetric
  - the `retrieve` node's span with ContextualRelevancyMetric

This produces per-node scores aligned with the 7 trace steps already shown
in the frontend TraceChain UI.
"""
import pytest
from deepeval.metrics import AnswerRelevancyMetric, ContextualRelevancyMetric
from deepeval.test_case import LLMTestCase

from .conftest import run_graph_for_question


def test_rag_component_level(golden_dataset, rag_graph, judge_llm):
    from deepeval.integrations.langchain import CallbackHandler
    from deepeval.tracing import next_llm_span

    failures = []
    for golden in golden_dataset:
        question = golden["input"]
        expected = golden.get("expected_output", "")

        answer_relevancy = AnswerRelevancyMetric(threshold=0.5, model=judge_llm)
        context_relevancy = ContextualRelevancyMetric(threshold=0.5, model=judge_llm)

        handler = CallbackHandler(metrics=[context_relevancy])

        with next_llm_span(metrics=[answer_relevancy]):
            final_state = rag_graph.invoke(
                {
                    "question": question,
                    "messages": [],
                    "documents": [],
                    "web_search_urls": [],
                    "generation": None,
                    "trace": [],
                    "steps": 0,
                    "web_search_enabled": False,
                    "max_loops": 3,
                },
                config={"callbacks": [handler]},
            )

        actual_output = final_state.get("generation", "")
        docs = final_state.get("documents", [])
        retrieval_context = [d["content"] for d in docs] if docs else []

        test_case = LLMTestCase(
            input=question,
            expected_output=expected,
            actual_output=actual_output,
            retrieval_context=retrieval_context if retrieval_context else ["No context retrieved."],
        )

        try:
            answer_relevancy.measure(test_case)
            assert answer_relevancy.is_successful(), (
                f"AnswerRelevancy for generate node: {answer_relevancy.score:.2f} - {answer_relevancy.reason}"
            )
            context_relevancy.measure(test_case)
            assert context_relevancy.is_successful(), (
                f"ContextualRelevancy for retrieve node: {context_relevancy.score:.2f} - {context_relevancy.reason}"
            )
        except AssertionError as e:
            failures.append(f"Q: {question}\n  {e}")

    if failures:
        pytest.fail(
            f"{len(failures)}/{len(golden_dataset)} goldens failed at component level:\n\n"
            + "\n\n".join(failures)
        )