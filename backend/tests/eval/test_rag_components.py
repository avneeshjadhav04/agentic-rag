"""Component-level RAG evaluation with DeepEval.

Scores two components of the Agentic RAG pipeline over the golden dataset:
  - the `generate` node's output via AnswerRelevancyMetric
  - the `retrieve` node's output via ContextualRelevancyMetric

Both metrics are scored on the same final LLMTestCase (input, actual_output,
retrieval_context) produced by a single graph invocation. DeepEval's
LangGraph callback/tracing integration was previously wired in here but had
no effect on the scores (the metrics were measured manually afterward), so
it has been removed to avoid implying per-node trace-scoped scoring that was
not actually happening.
"""
import pytest
from deepeval.metrics import AnswerRelevancyMetric, ContextualRelevancyMetric
from deepeval.test_case import LLMTestCase

from app.eval.runner import run_graph_for_question


def test_rag_component_level(golden_dataset, rag_graph, judge_llm):
    failures = []
    for golden in golden_dataset:
        question = golden["input"]
        expected = golden.get("expected_output", "")

        answer_relevancy = AnswerRelevancyMetric(threshold=0.5, model=judge_llm, async_mode=False)
        context_relevancy = ContextualRelevancyMetric(threshold=0.5, model=judge_llm, async_mode=False)

        final_state = run_graph_for_question(rag_graph, question)
        actual_output = final_state.get("generation", "")
        docs = final_state.get("documents", [])
        retrieval_context = [d["content"] for d in docs] if docs else []

        test_case = LLMTestCase(
            input=question,
            expected_output=expected,
            actual_output=actual_output,
            retrieval_context=retrieval_context,
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