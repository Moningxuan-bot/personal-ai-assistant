from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator
import json


@dataclass
class ChatMessage:
    role: str  # "system", "user", "assistant"
    content: str


class LLMProvider(ABC):
    """Abstract LLM provider — swap DeepSeek for Claude/OpenAI/etc."""

    @abstractmethod
    async def chat(
        self, messages: list[ChatMessage], stream: bool = False
    ) -> str | AsyncIterator[str]:
        """Send messages, return full response or stream chunks."""
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Convert text to embedding vector."""
        ...


class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            import httpx

            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def chat(
        self, messages: list[ChatMessage], stream: bool = False
    ) -> str | AsyncIterator[str]:
        client = self._get_client()
        body = {
            "model": "deepseek-chat",
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
        }
        if stream:
            return self._stream_chat(client, body)
        else:
            resp = await client.post("/v1/chat/completions", json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _stream_chat(self, client, body) -> AsyncIterator[str]:
        async def generate():
            async with client.stream("POST", "/v1/chat/completions", json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]

        return generate()

    async def embed(self, text: str) -> list[float]:
        """DeepSeek doesn't have a dedicated embedding API yet.
        Use EmbeddingProvider for embeddings."""
        raise NotImplementedError("Use EmbeddingProvider for embeddings")


# ---- singleton factory ----

_llm_instance: DeepSeekProvider | None = None


def get_llm() -> DeepSeekProvider:
    """返回全局共享的 DeepSeekProvider 单例（复用 httpx 连接池）。"""
    global _llm_instance
    if _llm_instance is None:
        from app.config import settings

        _llm_instance = DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    return _llm_instance
