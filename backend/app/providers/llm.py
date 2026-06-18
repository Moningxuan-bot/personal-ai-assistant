from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator
import json
import logging
import time

logger = logging.getLogger("ajiur.llm")


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
            return self._stream_chat_instrumented(client, body)
        else:
            return await self._chat_instrumented(client, body)

    async def _chat_instrumented(self, client, body: dict) -> str:
        start = time.time()
        status_code = 0
        error_type = None
        try:
            resp = await client.post("/v1/chat/completions", json=body)
            status_code = resp.status_code
            resp.raise_for_status()
            data = resp.json()
            result = data["choices"][0]["message"]["content"]
            return result
        except Exception as e:
            error_type = type(e).__name__
            raise
        finally:
            elapsed = round((time.time() - start) * 1000)
            msg_count = len(body["messages"])
            logger.info(
                f"LLM chat: stream=false msgs={msg_count} status={status_code} "
                f"elapsed={elapsed}ms" + (f" error={error_type}" if error_type else ""),
                extra={
                    "extra_fields": {
                        "llm_model": body["model"],
                        "llm_stream": False,
                        "llm_msg_count": msg_count,
                        "llm_status": status_code,
                        "llm_elapsed_ms": elapsed,
                        "llm_error": error_type,
                    },
                },
            )

    async def _stream_chat_instrumented(self, client, body) -> AsyncIterator[str]:
        """流式 LLM 调用 + 埋点（记录 TTFB 和总耗时）。"""
        msg_count = len(body["messages"])
        logger.info(
            f"LLM chat: stream=true msgs={msg_count} starting...",
            extra={
                "extra_fields": {
                    "llm_model": body["model"],
                    "llm_stream": True,
                    "llm_msg_count": msg_count,
                    "llm_status": "streaming",
                },
            },
        )

        start = time.time()
        first_token = False
        status_code = 0
        error_type = None
        chunk_count = 0
        try:
            async with client.stream("POST", "/v1/chat/completions", json=body) as resp:
                status_code = resp.status_code
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            if not first_token:
                                first_token = True
                                ttfb = round((time.time() - start) * 1000)
                                logger.info(
                                    f"LLM stream first_token ttfb={ttfb}ms",
                                    extra={
                                        "extra_fields": {
                                            "llm_ttfb_ms": ttfb,
                                            "llm_status": "streaming",
                                        },
                                    },
                                )
                            chunk_count += 1
                            yield delta["content"]
        except Exception as e:
            error_type = type(e).__name__
            raise
        finally:
            elapsed = round((time.time() - start) * 1000)
            logger.info(
                f"LLM stream done: chunks={chunk_count} total_elapsed={elapsed}ms"
                + (f" error={error_type}" if error_type else ""),
                extra={
                    "extra_fields": {
                        "llm_model": body["model"],
                        "llm_stream": True,
                        "llm_msg_count": msg_count,
                        "llm_status": "error" if error_type else "ok",
                        "llm_elapsed_ms": elapsed,
                        "llm_chunks": chunk_count,
                        "llm_error": error_type,
                    },
                },
            )

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
