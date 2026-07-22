"""Provider presets for chat LLMs and embedding models.

The system is provider-agnostic. Every provider uses an OpenAI-compatible
client by supplying base_url, model, and api_key. Users may also define a
"custom" provider from the UI.
"""
from typing import Any


PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "nvidia-nim": {
        "name": "NVIDIA NIM",
        "chat": {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "default_model": "deepseek-ai/deepseek-v4-flash",
        },
        "evaluations": {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "default_model": "openai/gpt-oss-20b",
        },
        "embeddings": {
            "base_url": "https://integrate.api.nvidia.com/v1",
            "default_model": "nvidia/nemotron-3-embed-1b",
        },
    },
    "openai": {
        "name": "OpenAI",
        "chat": {
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o-mini",
        },
        "evaluations": {
            "base_url": "https://api.openai.com/v1",
            "default_model": "gpt-4o-mini",
        },
        "embeddings": {
            "base_url": "https://api.openai.com/v1",
            "default_model": "text-embedding-3-small",
        },
    },
    "ollama": {
        "name": "Ollama",
        "chat": {
            "base_url": "http://localhost:11434/v1",
            "default_model": "llama3.1",
        },
        "evaluations": {
            "base_url": "http://localhost:11434/v1",
            "default_model": "llama3.1",
        },
        "embeddings": {
            "base_url": "http://localhost:11434/v1",
            "default_model": "nomic-embed-text",
        },
    },
    "custom": {
        "name": "Custom",
        "chat": {
            "base_url": "",
            "default_model": "",
        },
        "evaluations": {
            "base_url": "",
            "default_model": "",
        },
        "embeddings": {
            "base_url": "",
            "default_model": "",
        },
    },
}


def get_provider_list() -> list[dict[str, Any]]:
    """Return provider metadata suitable for the frontend."""
    return [
        {
            "id": key,
            "name": data["name"],
            "chat": data["chat"],
            "evaluations": data["evaluations"],
            "embeddings": data["embeddings"],
        }
        for key, data in PROVIDER_PRESETS.items()
    ]
