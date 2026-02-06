"""Generate vector embeddings for articles."""

from typing import List

from google import genai

from ai_daily.config import config


class Embedder:
    """Generate vector embeddings using Google's embedding API."""

    def __init__(self):
        self.client = genai.Client(api_key=config.llm.google_api_key)
        self.model = config.llm.embedding_model

    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed.

        Returns:
            Vector embedding as list of floats.
        """
        text = text[:8000]

        response = await self.client.aio.models.embed_content(
            model=self.model,
            contents=text,
        )

        return response.embeddings[0].values

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of vector embeddings.
        """
        texts = [t[:8000] for t in texts]
        embeddings = []

        for text in texts:
            response = await self.client.aio.models.embed_content(
                model=self.model,
                contents=text,
            )
            embeddings.append(response.embeddings[0].values)

        return embeddings
