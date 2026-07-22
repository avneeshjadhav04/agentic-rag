"""End-to-end RAG evaluation with DeepEval.

For each golden question:
  1. Invoke the full Agentic RAG LangGraph (retrieve -> grade -> generate -> quality_check)
  2. Capture the generation + retrieved context
  3. Assert against 4 RAG metrics using an independent LLM-as-judge

Metrics:
  - AnswerRelevancyMetric     : is the answer relevant to the question?
  - FaithfulnessMetric        : is the answer grounded in the context (no hallucination)?
  - ContextualPrecisionMetric : are relevant chunks ranked higher?
  - ContextualRecallMetric    : does the context contain all info needed for the expected answer?
"""
import pytest
from deepeval import assert_test
from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
)
from deepeval.test_case import LLMTestCase

from app.eval.runner import run_graph_for_question


def _make_test_case(question, expected_output, actual_output, retrieval_context):
    return LLMTestCase(
        input=question,
        expected_output=expected_output,
        actual_output=actual_output,
        retrieval_context=retrieval_context if retrieval_context else ["No context retrieved."],
    )


def test_rag_end_to_end(golden_dataset, rag_graph, judge_llm):
    failures = []
    for golden in golden_dataset:
        question = golden["input"]
        expected = golden.get("expected_output", "")
        final_state = run_graph_for_question(rag_graph, question)
        actual_output = final_state.get("generation", "")
        docs = final_state.get("documents", [])
        retrieval_context = [d["content"] for d in docs] if docs else []

        metrics = [
            AnswerRelevancyMetric(threshold=0.5, model=judge_llm),
            FaithfulnessMetric(threshold=0.5, model=judge_llm),
        ]
        if expected:
            metrics.append(ContextualPrecisionMetric(threshold=0.5, model=judge_llm))
            metrics.append(ContextualRecallMetric(threshold=0.5, model=judge_llm))

        test_case = _make_test_case(question, expected, actual_output, retrieval_context)
        try:
            assert_test(test_case, metrics)
        except AssertionError as e:
            failures.append(f"Q: {question}\n  {e}")

    if failures:
        pytest.fail(f"{len(failures)}/{len(golden_dataset)} goldens failed:\n\n" + "\n\n".join(failures))