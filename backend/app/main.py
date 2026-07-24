"""FastAPI entry point for the Agentic RAG backend."""
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, config, eval, ingestion

app = FastAPI(title="Agentic RAG Backend", version="0.1.0")


# All GET endpoints return dynamic, frequently-changing data (eval results,
# source lists, provider configs). Prevent the browser, the Next.js rewrite
# proxy, and the PaaS edge proxy from serving stale cached responses — the
# canonical example is /api/eval/results being served from cache right after
# a run finishes, hiding the fresh on-disk file until the cache expires.
@app.middleware("http")
async def disable_get_cache(request: Request, call_next):
    response = await call_next(request)
    if request.method == "GET":
        response.headers["Cache-Control"] = "no-store"
    return response


# Allow all origins for local dev / single-container deploy.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(ingestion.router)
app.include_router(config.router)
app.include_router(eval.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Agentic RAG Backend"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("BACKEND_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
