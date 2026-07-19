"""Ingestion endpoints for files and URLs."""
from typing import List

from fastapi import APIRouter, File, Form, UploadFile

from app.ingestion.chunker import chunk_documents
from app.ingestion.loader import load_files, load_urls
from app.models.factory import get_embeddings
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
    file_entries: list[tuple[str, bytes]] = []
    for file in files:
        content = await file.read()
        file_entries.append((file.filename or "uploaded_file", content))

    documents, file_results = load_files(file_entries)
    chunks = chunk_documents(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    store = _build_store(embed_base_url, embed_model, embed_api_key)
    store.add_documents(chunks)
    return {"ingested": len(chunks), "files": file_results}


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
    chunks = chunk_documents(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    store = _build_store(embed_base_url, embed_model, embed_api_key)
    store.add_documents(chunks)
    return {"ingested": len(chunks), "url_count": len(url_list)}


@router.post("/clear")
async def clear_store(
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
):
    store = _build_store(embed_base_url, embed_model, embed_api_key)
    store.clear()
    return {"cleared": True}


@router.post("/list")
async def list_sources(
    embed_base_url: str = Form(...),
    embed_model: str = Form(...),
    embed_api_key: str = Form(default=""),
):
    store = _build_store(embed_base_url, embed_model, embed_api_key)
    try:
        all_data = store._get_store()._collection.get(include=["metadatas"])
        sources = sorted({
            m["source"] for m in all_data["metadatas"]
            if m and m.get("source")
        })
        return {"sources": sources, "total": len(sources)}
    except Exception as e:
        return {"sources": [], "total": 0, "error": str(e)}
