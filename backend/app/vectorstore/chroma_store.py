"""Chroma vector store wrapper."""
import os
from typing import List

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings


DEFAULT_PERSIST_DIR = "./chroma_db"


class ChromaStore:
    def __init__(self, embeddings: OpenAIEmbeddings, persist_dir: str = DEFAULT_PERSIST_DIR):
        self.embeddings = embeddings
        self.persist_dir = persist_dir
        self._store: Chroma | None = None

    def _get_store(self) -> Chroma:
        if self._store is None:
            os.makedirs(self.persist_dir, exist_ok=True)
            self._store = Chroma(
                embedding_function=self.embeddings,
                persist_directory=self.persist_dir,
                collection_name="agentic_rag",
            )
        return self._store

    def add_documents(self, documents: List[Document]) -> None:
        if not documents:
            return
        store = self._get_store()
        store.add_documents(documents)
        store.persist()

    def similarity_search(self, query: str, k: int = 4) -> List[Document]:
        store = self._get_store()
        return store.similarity_search(query, k=k)

    def clear(self) -> None:
        store = self._get_store()
        store.delete_collection()
        self._store = None
