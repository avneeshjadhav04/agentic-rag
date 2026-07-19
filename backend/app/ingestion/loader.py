"""Document loading and URL loading utilities."""
import os
import tempfile
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
)
from langchain_community.document_loaders.web_base import WebBaseLoader


def load_files(entries: List[Tuple[str, bytes]]) -> List[Document]:
    """Load documents from uploaded file entries (name, content)."""
    documents: List[Document] = []
    for original_name, content in entries:
        suffix = os.path.splitext(original_name)[1] or ".txt"
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            if suffix.lower() == ".pdf":
                loader = PyPDFLoader(tmp_path)
            else:
                loader = TextLoader(tmp_path, encoding="utf-8", autodetect_encoding=True)
            documents.extend(loader.load())
        except Exception:
            continue
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
    return documents


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
            documents.extend(docs)
        except Exception:
            # Best-effort: skip URLs that fail to load.
            continue
    return documents
