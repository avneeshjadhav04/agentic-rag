"""Environment-level default config for chat and embedding providers.

Every value can be overridden via a DEFAULT_* env var.  If the env var is
not set the hardcoded fallback below is used.  The frontend fetches this
endpoint once on mount and merges the values into the Zustand store
*only* for fields the user has not yet touched (i.e. fields that still
match the hardcoded defaults).

User changes in the UI always win over both env vars and hardcoded values.
"""
import os
from typing import Any

HARDCODED_GENERATION: dict[str, Any] = {
    "provider": "nvidia-nim",
    "baseUrl": "https://integrate.api.nvidia.com/v1",
    "model": "openai/gpt-oss-20b",
    "apiKey": "",
}

HARDCODED_EVALUATION: dict[str, Any] = {
    "provider": "nvidia-nim",
    "baseUrl": "https://integrate.api.nvidia.com/v1",
    "model": "openai/gpt-oss-20b",
    "apiKey": "",
}

HARDCODED_EMBEDDING: dict[str, Any] = {
    "provider": "nvidia-nim",
    "baseUrl": "https://integrate.api.nvidia.com/v1",
    "model": "nvidia/nemotron-3-embed-1b",
    "apiKey": "",
}


def get_default_config() -> dict[str, Any]:
    return {
        "generation": {
            "provider": os.environ.get("DEFAULT_GENERATION_PROVIDER", HARDCODED_GENERATION["provider"]),
            "baseUrl": os.environ.get("DEFAULT_GENERATION_BASE_URL", HARDCODED_GENERATION["baseUrl"]),
            "model": os.environ.get("DEFAULT_GENERATION_MODEL", HARDCODED_GENERATION["model"]),
            "apiKey": os.environ.get("DEFAULT_GENERATION_API_KEY", HARDCODED_GENERATION["apiKey"]),
        },
        "evaluation": {
            "provider": os.environ.get("DEFAULT_EVALUATION_PROVIDER", HARDCODED_EVALUATION["provider"]),
            "baseUrl": os.environ.get("DEFAULT_EVALUATION_BASE_URL", HARDCODED_EVALUATION["baseUrl"]),
            "model": os.environ.get("DEFAULT_EVALUATION_MODEL", HARDCODED_EVALUATION["model"]),
            "apiKey": os.environ.get("DEFAULT_EVALUATION_API_KEY", HARDCODED_EVALUATION["apiKey"]),
        },
        "embedding": {
            "provider": os.environ.get("DEFAULT_EMBEDDING_PROVIDER", HARDCODED_EMBEDDING["provider"]),
            "baseUrl": os.environ.get("DEFAULT_EMBEDDING_BASE_URL", HARDCODED_EMBEDDING["baseUrl"]),
            "model": os.environ.get("DEFAULT_EMBEDDING_MODEL", HARDCODED_EMBEDDING["model"]),
            "apiKey": os.environ.get("DEFAULT_EMBEDDING_API_KEY", HARDCODED_EMBEDDING["apiKey"]),
        },
    }
