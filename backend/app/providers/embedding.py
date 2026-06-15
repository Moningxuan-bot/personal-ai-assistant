from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract embedding provider — local model or API."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...


class SentenceTransformerProvider(EmbeddingProvider):
    """Local embedding using sentence-transformers (lightweight, free, bge-small-zh)."""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    async def embed(self, text: str) -> list[float]:
        import asyncio

        model = self._load_model()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, model.encode, text)
        return result.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        model = self._load_model()
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, model.encode, texts)
        return [r.tolist() for r in results]
