"""Chroma vector store wrapper."""
import os
import uuid
from typing import Callable, List, Optional

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
        try:
            store.persist()
        except (NotImplementedError, AttributeError):
            print("ChromaDB>=0.5 auto-persists; skipping explicit persist().")

    def add_documents_with_progress(
        self,
        documents: List[Document],
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        """Add documents one-by-one, emitting progress per chunk.

        Embeds each document individually via embed_query and adds it
        directly to the Chroma collection, bypassing LangChain's batch
        add_documents path. This lets the caller stream progress events
        during long ingestions (e.g., 100+ chunks) so the SSE connection
        stays alive and the user sees live progress.

        Returns the number of documents successfully added.
        """
        if not documents:
            return 0
        store = self._get_store()
        collection = store._collection
        added = 0
        total = len(documents)
        for i, doc in enumerate(documents):
            text = doc.page_content or ""
            embedding = self.embeddings.embed_query(text)
            chunk_id = str(uuid.uuid4())
            collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[text],
                metadatas=[doc.metadata or {}],
            )
            added += 1
            if progress_callback:
                progress_callback({
                    "stage": "embedding",
                    "current": added,
                    "total": total,
                })
        try:
            store.persist()
        except (NotImplementedError, AttributeError):
            print("ChromaDB>=0.5 auto-persists; skipping explicit persist().")
        return added

    def similarity_search(self, query: str, k: int = 4) -> List[Document]:
        store = self._get_store()
        return store.similarity_search(query, k=k)

    def clear(self) -> None:
        store = self._get_store()
        store.delete_collection()
        self._store = None

    def delete_by_source(self, source_id: str) -> None:
        store = self._get_store()
        collection = store._collection
        results = collection.get(where={"source_id": source_id})
        ids = results.get("ids", [])
        if ids:
            collection.delete(ids=ids)
