"""Provider-agnostic factories for chat LLMs and embedding models."""
from typing import List, Optional

from openai import OpenAI
from langchain_openai import ChatOpenAI, OpenAIEmbeddings


def get_generation_llm(
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


def get_eval_llm(
    base_url: str,
    model: str,
    api_key: str,
    temperature: float = 0.0,
    max_tokens: Optional[int] = 2048,
) -> ChatOpenAI:
    """LLM used as the DeepEval judge. Non-streaming, low temperature for stable scoring."""
    if not base_url or not model:
        raise ValueError("base_url and model are required")
    return ChatOpenAI(
        base_url=base_url,
        model=model,
        api_key=api_key or "dummy",
        temperature=temperature,
        max_tokens=max_tokens,
        streaming=False,
    )


class NvidiaEmbeddings(OpenAIEmbeddings):
    """Override to send input as string — NVIDIA NIM rejects arrays."""

    def __init__(self, **kwargs):
        api_key = kwargs.pop("api_key", None) or kwargs.pop("openai_api_key", None) or "dummy"
        base_url = kwargs.pop("base_url", None) or kwargs.pop("openai_api_base", None) or ""
        kwargs.setdefault("openai_api_key", api_key)
        kwargs.setdefault("openai_api_base", base_url)
        super().__init__(**kwargs)
        self._nvidia_client = OpenAI(api_key=api_key, base_url=base_url)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        responses = []
        for text in texts:
            data = self._nvidia_client.embeddings.create(
                input=text,
                model=self.model,
            )
            responses.append(data.data[0].embedding)
        return responses

    def embed_query(self, text: str) -> List[float]:
        data = self._nvidia_client.embeddings.create(
            input=text,
            model=self.model,
        )
        return data.data[0].embedding


def get_embeddings(base_url: str, model: str, api_key: str) -> NvidiaEmbeddings:
    if not base_url or not model:
        raise ValueError("base_url and model are required")
    return NvidiaEmbeddings(
        base_url=base_url,
        model=model,
        api_key=api_key or "dummy",
    )
