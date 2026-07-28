"""Text splitting utilities."""
from collections import defaultdict

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_documents(documents: list[Document], chunk_size: int = 1000, chunk_overlap: int = 200) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        add_start_index=True,
    )
    return splitter.split_documents(documents)


def chunk_documents_parent_child(
    documents: list[Document],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> tuple[list[Document], list[Document]]:
    """Split documents into child chunks for indexing and parent docs for
    generation context.

    Children are produced by ``RecursiveCharacterTextSplitter`` (unchanged
    behavior) and inherit each input document's ``source_id`` metadata, so
    child -> parent linking is automatic (no extra metadata field needed).

    Parents are the full concatenated content of every input document sharing
    the same ``source_id`` (i.e. one parent per uploaded source file). This
    keeps semantic units whole so a split list, table, or argument is returned
    to the grader/generator as a single coherent document instead of a
    fragment. The retrieve node applies ``PARENT_CHAR_CAP`` to fall back to a
    neighbor-window for oversized parents.

    Returns ``(child_chunks, parent_docs)``.
    """
    child_chunks = chunk_documents(documents, chunk_size, chunk_overlap)

    grouped: dict[str, list[Document]] = defaultdict(list)
    for doc in documents:
        sid = doc.metadata.get("source_id")
        if sid is None:
            continue
        grouped[sid].append(doc)

    parent_docs: list[Document] = []
    for sid, group in grouped.items():
        combined = "\n".join(d.page_content for d in group)
        parent_meta = dict(group[0].metadata)
        parent_meta.pop("start_index", None)
        parent_docs.append(Document(page_content=combined, metadata=parent_meta))

    return child_chunks, parent_docs
