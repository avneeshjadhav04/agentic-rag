"""Ingestion endpoints for files and URLs."""
from typing import Callable, List

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from app.ingestion.chunker import chunk_documents_parent_child
from app.ingestion.loader import load_files, load_urls
from app.models.factory import get_embeddings
from app.sse import SSE_HEADERS, stream_threaded
from app.vectorstore.chroma_store import ChromaStore

router = APIRouter(prefix="/api/ingest", tags=["ingestion"])


def _build_store(
    embed_base_url: str,
    embed_model: str,
    embed_api_key: str,
) -> ChromaStore:
    embeddings = get_embeddings(embed_base_url, embed_model, embed_api_key)
    return ChromaStore(embeddings=embeddings)


@router.post("/files")
async def ingest_files(
    files: List[UploadFile] = File(...),
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
    chunk_size: int = Form(default=1000),
    chunk_overlap: int = Form(default=200),
):
    # Read uploaded files in the async endpoint (UploadFile.read is async),
    # then stream the blocking load→chunk→embed work via SSE so the proxy
    # doesn't kill the idle connection on large files (100+ chunks can take
    # 20-50s of sequential embedding calls).
    file_entries: list[tuple[str, bytes]] = []
    for file in files:
        content = await file.read()
        file_entries.append((file.filename or "uploaded_file", content))

    def target(progress_callback: Callable[[dict], None]) -> dict:
        progress_callback({"stage": "loading", "message": "Parsing uploaded files…"})
        documents, file_results = load_files(file_entries)

        progress_callback({"stage": "chunking", "message": f"Splitting {len(documents)} documents into chunks…"})
        child_chunks, parent_docs = chunk_documents_parent_child(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        if not child_chunks:
            return {"ingested": 0, "files": file_results}

        progress_callback({"stage": "embedding", "current": 0, "total": len(child_chunks)})
        store = _build_store(embed_base_url, embed_model, embed_api_key)
        added = store.add_parent_child_documents(child_chunks, parent_docs, progress_callback=progress_callback)
        return {"ingested": added, "files": file_results}

    return StreamingResponse(stream_threaded(target), media_type="text/event-stream", headers=SSE_HEADERS)


@router.post("/urls")
async def ingest_urls(
    urls: str = Form(...),
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
    chunk_size: int = Form(default=1000),
    chunk_overlap: int = Form(default=200),
):
    url_list = [u.strip() for u in urls.replace(",", "\n").splitlines() if u.strip()]
    documents = load_urls(url_list)
    child_chunks, parent_docs = chunk_documents_parent_child(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    store = _build_store(embed_base_url, embed_model, embed_api_key)
    store.add_parent_child_documents(child_chunks, parent_docs)
    return {"ingested": len(child_chunks), "url_count": len(url_list)}


@router.post("/clear")
async def clear_store(
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
):
    store = _build_store(embed_base_url, embed_model, embed_api_key)
    store.clear()
    return {"cleared": True}


@router.post("/delete-source")
async def delete_source(
    source_id: str = Form(...),
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
):
    store = _build_store(embed_base_url, embed_model, embed_api_key)
    store.delete_by_source(source_id)
    return {"deleted": True}


@router.post("/list")
async def list_sources(
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
):
    store = _build_store(embed_base_url, embed_model, embed_api_key)
    try:
        all_data = store._get_store()._collection.get(include=["metadatas"])
        seen = set()
        sources = []
        for m in all_data["metadatas"]:
            if m and m.get("source_id") and m.get("source"):
                sid = m["source_id"]
                if sid not in seen:
                    seen.add(sid)
                    sources.append({"source_id": sid, "name": m["source"]})
        sources.sort(key=lambda s: s["name"])
        return {"sources": sources, "total": len(sources)}
    except Exception as e:
        return {"sources": [], "total": 0, "error": str(e)}
