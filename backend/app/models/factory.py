"""Provider-agnostic factories for chat LLMs and embedding models."""
from typing import Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings


def get_chat_llm(
    base_url: str,
    model: str,
    api_key: str,
    temperature: float = 0.7,
    max_tokens: Optional[int] = 1024,
) -> ChatOpenAI:
    if not base_url or not model:
        raise ValueError("base_url and model are required")
    return ChatOpenAI(
        base_url=base_url,
        model=model,
        api_key=api_key or "dummy",
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=True,
    )


def get_embeddings(base_url: str, model: str, api_key: str) -> OpenAIEmbeddings:
    if not base_url or not model:
        raise ValueError("base_url and model are required")
    return OpenAIEmbeddings(
        base_url=base_url,
        model=model,
        api_key=api_key or "dummy",
    )
