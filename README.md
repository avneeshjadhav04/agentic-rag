# Agentic RAG

![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C1917?logo=langchain&logoColor=white)
![Chroma](https://img.shields.io/badge/Chroma-FF6F00?logo=chromadb&logoColor=white)
![Next.js 14](https://img.shields.io/badge/Next.js_14-000000?logo=nextdotjs&logoColor=white)
![DeepEval](https://img.shields.io/badge/DeepEval-7C3AED?logoColor=white)

Agentic RAG is a retrieval-augmented generation chat agent built with LangGraph,
FastAPI, and Next.js. It retrieves relevant documents from a Chroma vector store,
grades them for relevance, generates an answer grounded in that context, and
self-corrects via a quality-check loop when the answer falls short.

## Features

- **Agentic retrieval pipeline** — LangGraph workflow with retrieve, grade,
  generate, and quality-check nodes; self-corrects with a refined question up to
  3 times when the answer isn't grounded.
- **Streaming responses** — token-by-token answer streaming with live per-node
  trace visualization (retrieve, grade, generate, quality check).
- **Web-fetch fallback** — when retrieved docs are irrelevant, the agent
  proposes and fetches web URLs, re-grades them, and uses the relevant content.
- **Markdown chat rendering** — GitHub-flavored markdown with syntax-highlighted
  code blocks and a streaming cursor.
- **Multi-format ingestion** — upload PDF, DOCX, DOC, and TXT files or paste
  URLs; live SSE progress shows parsing, chunking, and embedding stages.
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