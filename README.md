# Agentic RAG

![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C1917?logo=langchain&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain_≥1.0-1C1917?logo=langchain&logoColor=white)
![Chroma](https://img.shields.io/badge/Chroma-FF6F00?logo=chromadb&logoColor=white)
![Next.js 14](https://img.shields.io/badge/Next.js_14-000000?logo=nextdotjs&logoColor=white)
![DeepEval](https://img.shields.io/badge/DeepEval-7C3AED?logoColor=white)

Agentic RAG is a retrieval-augmented generation system built with LangChain,
LangGraph, FastAPI, and Next.js.

## Features

- **Multi-agent architecture** — LangGraph workflow with a main agent
  (supervisor) coordinating a research subagent (retrieval + grading) and a
  writer subagent (generation), with a deterministic quality-check node that
  self-corrects up to 3 times via `QualityFeedbackMessage`.
- **Parent-child retrieval** — child chunks (1000 chars / 200 overlap) are
  embedded for search precision; parent documents are expanded at query time
  for answer coherence, with a sliding-window fallback for large parents.
- **Streaming responses** — token-by-token answer streaming with live per-step
  trace visualization (research, research_result, draft, draft_result,
  tool_result, quality_check) via SSE.
- **Stop button** — graceful shutdown via a `threading.Event` threaded through
  `WorkflowState`; in-flight tools short-circuit with `[Stopped]` messages
  instead of force-killing the thread.
- **Web-fetch fallback** — when local results are insufficient, the research
  subagent can propose and fetch specific web URLs, re-grade them, and use the
  relevant content.
- **Markdown chat rendering** — GitHub-flavored markdown with syntax-highlighted
  code blocks and a streaming cursor.
- **Multi-format ingestion** — upload PDF, DOCX, DOC, and TXT files or paste
  URLs; live SSE progress shows loading, chunking, and embedding stages.
- **Per-source management** — list, delete, or clear individual ingested sources
  from the vector store.
- **Configurable chunking** — chunk size and overlap are adjustable per
  ingestion.
- **RAG evaluation** — DeepEval harness with golden-dataset generation, four
  metrics (answer relevancy, faithfulness, contextual precision, contextual
  recall), and persisted run results.
- **Three-provider model** — separate, swappable configs for generation,
  evaluation (judge), and embedding to avoid judge bias.
- **Multi-provider support** — NVIDIA NIM, OpenAI, Ollama, or any
  OpenAI-compatible endpoint configurable via the UI.
- **Single-container deployment** — one Docker image runs FastAPI and Next.js
  standalone under supervisord, deployable to Railway or Render.

## Branching Strategy

- `main` — production-ready code.
- `develop` — active development branch; feature work integrates here before
  promoting to `main`.