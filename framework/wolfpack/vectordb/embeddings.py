"""Embeddings abstraction. MVP: OpenAI embeddings; extensible with other providers
(Ollama, Cohere, etc.) (wolfpack `Model` pattern but for vectors).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import List


class EmbeddingModel(ABC):
    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        ...


class OpenAIEmbeddingModel(EmbeddingModel):
    def __init__(self, model: str, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.model = model
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError('Instalá "openai>=1.40" para embeddings OpenAI.') from e
        kwargs = {"api_key": self.api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)

    def embed(self, texts: List[str]) -> List[List[float]]:
        resp = self._client.embeddings.create(model=self.model, input=texts)
        return [d.embedding for d in resp.data]


class OllamaEmbeddingModel(EmbeddingModel):
    """Ollama embeddings via the OpenAI-compatible `/v1/embeddings` endpoint.

    Works with remote servers (OLLAMA_BASE_URL) as well as localhost. Sends all
    texts in a single request (batching). A browser-like User-Agent is used so
    proxies/cloud gateways that block the default Python-urllib client do not
    reject the request (Ollama reverse proxies commonly return 403 otherwise).
    """

    def __init__(self, model: str, host: Optional[str] = None, user_agent: str = "Mozilla/5.0 (wolfpack-ai)"):
        self.model = model
        self.host = host or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.user_agent = user_agent

    def embed(self, texts: List[str]) -> List[List[float]]:
        import json
        import urllib.request

        base = self.host.rstrip("/")
        body = json.dumps({"model": self.model, "input": list(texts)}).encode()
        req = urllib.request.Request(
            f"{base}/v1/embeddings",
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": self.user_agent},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())
        return [item["embedding"] for item in data["data"]]


class HuggingFaceEmbeddingModel(EmbeddingModel):
    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model = model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError('Instalá "sentence-transformers" para usar embeddings locales.') from e
        self._enc = SentenceTransformer(model)

    def embed(self, texts: List[str]) -> List[List[float]]:
        return self._enc.encode(texts, convert_to_numpy=False).tolist()