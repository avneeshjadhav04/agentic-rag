# RAG Evaluation Harness

Offline RAG evaluation using [DeepEval](https://github.com/confident-ai/deepeval) (Apache 2.0).

## What it measures

**End-to-end** (`test_rag_e2e.py`):
| Metric | What it scores |
|---|---|
| AnswerRelevancyMetric | Is the generated answer relevant to the question? |
| FaithfulnessMetric | Is the answer grounded in retrieved context (no hallucination)? |
| ContextualPrecisionMetric | Are relevant chunks ranked higher in retrieval? |
| ContextualRecallMetric | Does retrieved context contain all info needed for the expected answer? |

**Component-level** (`test_rag_components.py`):
| Metric | Target node |
|---|---|
| AnswerRelevancyMetric | `generate` node's LLM span |
| ContextualRelevancyMetric | `retrieve` node's span |

All metrics output a 0-1 score + LLM-judge reasoning; pass/fail at threshold 0.5.

## Three-provider model

The eval harness uses **three independent provider configs** to avoid judge bias:

| Provider | Used for | Env vars |
|---|---|---|
| Generation | The RAG pipeline's LLM (generate, grade, quality_check) | `DEFAULT_GENERATION_*` |
| Evaluation | The DeepEval LLM-as-judge | `DEFAULT_EVALUATION_*` |
| Embedding | Chroma vector store | `DEFAULT_EMBEDDING_*` |

All three default to NVIDIA NIM. Override any via env vars or the UI sidebar.

## Running

### 1. Generate the golden dataset (one-time)

```bash
cd backend
python -m tests.eval.generate_goldens
```

This reads chunks from your live Chroma store and synthesizes ~20 goldens
via DeepEval's `Synthesizer`, writing `golden_dataset.json` in this directory.
**Curate the goldens before committing** — they are the ground truth for all metrics.

### 2. Run the evaluations

```bash
cd backend
deepeval test run tests/eval/
```

Or via the wrapper:

```bash
./scripts/eval.sh
```

Results are written as **local JSON** to `.deepeval/` (set `DEEPEVAL_RESULTS_FOLDER` to override).

## Confident AI — intentionally excluded

DeepEval optionally pushes results to [Confident AI](https://www.confident-ai.com),
a proprietary hosted dashboard. This project **does not use it**. All results stay
local. Do not run `deepeval login`.