"""Document loading and URL loading utilities."""
import os
import tempfile
import uuid
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    Docx2txtLoader,
    PDFPlumberLoader,
    TextLoader,
)
from langchain_community.document_loaders.web_base import WebBaseLoader


def load_files(entries: List[Tuple[str, bytes]]) -> tuple[List[Document], list[dict]]:
    """Load documents from uploaded file entries (name, content).

    Returns (documents, results) where results has per-file status.
    """
    documents: List[Document] = []
    results: list[dict] = []
    for original_name, content in entries:
        suffix = os.path.splitext(original_name)[1].lower() or ".txt"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            if suffix == ".pdf":
                loader = PDFPlumberLoader(tmp_path)
            elif suffix in (".docx", ".doc"):
                loader = Docx2txtLoader(tmp_path)
            else:
                loader = TextLoader(tmp_path, encoding="utf-8", autodetect_encoding=True)
            loaded = loader.load()
            if loaded and all(not (d.page_content or "").strip() for d in loaded):
                results.append({"file": original_name, "chunks": 0, "status": "warning", "error": "File loaded but all pages have empty text (scanned document or binary format)"})
                continue
            documents.extend(loaded)
            source_id = str(uuid.uuid4())
            for doc in loaded:
                doc.metadata["source"] = original_name
                doc.metadata["source_id"] = source_id
            results.append({"file": original_name, "chunks": len(loaded), "status": "ok"})
        except Exception as e:
            results.append({"file": original_name, "chunks": 0, "status": "error", "error": repr(e)[:200]})
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
    return documents, results


def load_urls(urls: List[str]) -> List[Document]:
    """Load documents from a list of URLs."""
    documents: List[Document] = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        try:
            loader = WebBaseLoader(url)
            docs = loader.load()
            source_id = str(uuid.uuid4())
            for doc in docs:
                doc.metadata["source"] = url
                doc.metadata["source_id"] = source_id
            documents.extend(docs)
        except Exception:
            continue
    return documents
