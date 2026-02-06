"""Generate vector embeddings for articles."""

from typing import List

import google.generativeai as genai

from ai_daily.config import config


class Embedder:
    """Generate vector embeddings using Google's embedding API."""

    def __init__(self):
        genai.configure(api_key=config.llm.google_api_key)
        self.model = config.llm.embedding_model

    async def embed(self, text: str) -> List[float]:
        """Generate embedding for text.

        Args:
            text: Text to embed.

        Returns:
            Vector embedding as list of floats.
        """
        text = text[:8000]

        result = genai.embed_content(
            model=f"models/{self.model}",
            content=text,
            task_type="RETRIEVAL_DOCUMENT",
        )

        return result["embedding"]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of vector embeddings.
        """
        texts = [t[:8000] for t in texts]

        result = genai.embed_content(
            model=f"models/{self.model}",
            content=texts,
            task_type="RETRIEVAL_DOCUMENT",
        )

        return result["embedding"]
