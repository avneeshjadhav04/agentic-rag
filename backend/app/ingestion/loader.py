"""Document loading and URL loading utilities."""
import io
import os
import tempfile
from typing import List

import requests
from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredMarkdownLoader,
)
from langchain_community.document_loaders.web_base import WebBaseLoader


def load_files(files: List[io.BytesIO]) -> List[Document]:
    """Load documents from uploaded file-like objects."""
    documents: List[Document] = []
    for file in files:
        original_name = getattr(file, "name", "uploaded_file")
        suffix = os.path.splitext(original_name)[1] or ".txt"
        content = file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            if suffix.lower() == ".pdf":
                loader = PyPDFLoader(tmp_path)
            elif suffix.lower() in (".md", ".markdown"):
                loader = UnstructuredMarkdownLoader(tmp_path)
            else:
                loader = TextLoader(tmp_path, encoding="utf-8", autodetect_encoding=True)
            documents.extend(loader.load())
        finally:
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
