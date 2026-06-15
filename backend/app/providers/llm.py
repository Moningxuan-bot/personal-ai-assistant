from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


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

    async def _stream_chat(self, client, body):
        async def generate():
            async with client.stream("POST", "/v1/chat/completions", json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        import json

                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]

        return generate()

    async def embed(self, text: str) -> list[float]:
        """DeepSeek doesn't have a dedicated embedding API yet.
        Use EmbeddingProvider for embeddings."""
        raise NotImplementedError("Use EmbeddingProvider for embeddings")
