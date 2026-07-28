"""Chroma vector store wrapper."""
import json
import os
import uuid
from pathlib import Path
from typing import Callable, Dict, List, Optional

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings


DEFAULT_PERSIST_DIR = "./chroma_db"

# Parent-document retrieval configuration.
# Parents are the full uploaded document; if one exceeds this cap (chars),
# the retrieve node falls back to a window of neighboring child chunks.
PARENT_CHAR_CAP = 16000
# Half-window size: returns child_idx +/- WINDOW_RADIUS neighbors.
WINDOW_RADIUS = 2


class ChromaStore:
    def __init__(self, embeddings: OpenAIEmbeddings, persist_dir: str = DEFAULT_PERSIST_DIR):
        self.embeddings = embeddings
        self.persist_dir = persist_dir
        self._store: Chroma | None = None
        self._parents_path = Path(persist_dir) / "parents.json"
        self._parents_cache: Optional[Dict[str, dict]] = None

    def _get_store(self) -> Chroma:
        if self._store is None:
            os.makedirs(self.persist_dir, exist_ok=True)
            self._store = Chroma(
                embedding_function=self.embeddings,
                persist_directory=self.persist_dir,
                collection_name="agentic_rag",
            )
        return self._store

    # ------------------------------------------------------------------
    # Parent-doc store (JSON sidecar)
    # ------------------------------------------------------------------
    def _load_parents(self) -> Dict[str, dict]:
        if self._parents_cache is not None:
            return self._parents_cache
        if not self._parents_path.exists():
            self._parents_cache = {}
            return self._parents_cache
        try:
            with open(self._parents_path, "r", encoding="utf-8") as f:
                self._parents_cache = json.load(f)
        except (json.JSONDecodeError, OSError):
            self._parents_cache = {}
        return self._parents_cache

    def _save_parents(self) -> None:
        if self._parents_cache is None:
            return
        os.makedirs(self.persist_dir, exist_ok=True)
        with open(self._parents_path, "w", encoding="utf-8") as f:
            json.dump(self._parents_cache, f, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Ingestion
    # ------------------------------------------------------------------
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

    def add_parent_child_documents(
        self,
        child_chunks: List[Document],
        parent_docs: List[Document],
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> int:
        """Index child chunks in Chroma (for embedding search) and persist
        parent docs in a JSON sidecar (for coherent generation context).

        Parents are keyed by ``source_id`` (the same id present on each child
        chunk's metadata), so the retrieve node can fetch the parent for any
        retrieved child without an extra metadata field. Re-ingestion merges
        new parents into the existing sidecar.
        """
        added = self.add_documents_with_progress(child_chunks, progress_callback)

        parents = self._load_parents()
        for doc in parent_docs:
            sid = doc.metadata.get("source_id")
            if sid is None:
                continue
            parents[sid] = {
                "content": doc.page_content,
                "metadata": doc.metadata or {},
            }
        self._parents_cache = parents
        self._save_parents()
        return added

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def similarity_search(self, query: str, k: int = 4) -> List[Document]:
        store = self._get_store()
        return store.similarity_search(query, k=k)

    def get_parents(self, source_ids: List[str]) -> Dict[str, Document]:
        """Look up parent docs by source_id. Returns a dict keyed by source_id.
        Returns an empty dict if no parents.json exists (backward-compatible
        with stores ingested before parent-doc retrieval was added).
        """
        parents = self._load_parents()
        out: Dict[str, Document] = {}
        for sid in source_ids:
            entry = parents.get(sid)
            if entry:
                out[sid] = Document(
                    page_content=entry.get("content", ""),
                    metadata=entry.get("metadata", {}),
                )
        return out

    def get_all_parents(self) -> List[Document]:
        """Return all parent docs. Used by golden generation to synthesize
        goldens from coherent full-document context. Returns an empty list
        if no parents.json exists.
        """
        parents = self._load_parents()
        return [
            Document(page_content=e.get("content", ""), metadata=e.get("metadata", {}))
            for e in parents.values()
        ]

    def get_children_by_source(self, source_id: str) -> List[Document]:
        """Return all child chunks for a source_id, sorted by start_index.
        Used by the retrieve node's safety-cap window fallback.
        """
        store = self._get_store()
        collection = store._collection
        results = collection.get(
            where={"source_id": source_id},
            include=["documents", "metadatas"],
        )
        docs: List[Document] = []
        for text, meta in zip(results.get("documents", []), results.get("metadatas", [])):
            docs.append(Document(page_content=text, metadata=meta or {}))
        docs.sort(key=lambda d: d.metadata.get("start_index", 0))
        return docs

    # ------------------------------------------------------------------
    # Store management
    # ------------------------------------------------------------------
    def clear(self) -> None:
        store = self._get_store()
        store.delete_collection()
        self._store = None
        if self._parents_path.exists():
            try:
                self._parents_path.unlink()
            except OSError:
                pass
        self._parents_cache = None

    def delete_by_source(self, source_id: str) -> None:
        store = self._get_store()
        collection = store._collection
        results = collection.get(where={"source_id": source_id})
        ids = results.get("ids", [])
        if ids:
            collection.delete(ids=ids)
        parents = self._load_parents()
        if source_id in parents:
            parents.pop(source_id)
            self._parents_cache = parents
            self._save_parents()
