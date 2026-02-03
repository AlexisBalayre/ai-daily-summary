"""Generate vector embeddings for articles."""

from typing import List

from openai import AsyncOpenAI

from ai_daily.config import config


class Embedder:
    """Generate vector embeddings using OpenAI or Ollama."""

    def __init__(self):
        if config.llm.provider == "ollama":
            self.client = AsyncOpenAI(
                base_url=config.llm.ollama_base_url,
                api_key="ollama"
            )
            self.model = "nomic-embed-text"
        else:
            self.client = AsyncOpenAI()
            self.model = config.llm.embedding_model

    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed.

        Returns:
            Vector embedding as list of floats.
        """
        text = text[:8000]

        response = await self.client.embeddings.create(
            model=self.model,
            input=text,
        )

        return response.data[0].embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of vector embeddings.
        """
        texts = [t[:8000] for t in texts]

        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
        )

        return [d.embedding for d in response.data]
