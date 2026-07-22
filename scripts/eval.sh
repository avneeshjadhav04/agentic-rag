#!/usr/bin/env bash
set -e

# Run the DeepEval RAG evaluation harness.
# Results are written locally to .deepeval/ (no Confident AI cloud).
cd "$(dirname "$0")/../backend"
exec deepeval test run tests/eval/ "$@"