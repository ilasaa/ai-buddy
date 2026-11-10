"""Lazy CPU provider. Download only with explicit preload/index command."""

from functools import lru_cache
from threading import Lock

import numpy as np

from app.core.config import settings

_model_lock = Lock()


@lru_cache(maxsize=1)
def load_model(name: str, local_only: bool):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(
        name,
        device="cpu",
        local_files_only=local_only,
        trust_remote_code=False,
        cache_folder=settings.embedding_cache_dir,
    )


class Embeddings:
    @property
    def model(self):
        # lru_cache alone permits duplicate concurrent first loads.
        with _model_lock:
            return load_model(settings.embedding_model, settings.embedding_local_only)

    def tokens(self, text: str) -> list[int]:
        return self.model.tokenizer.encode(text, add_special_tokens=False)

    def decode(self, tokens: list[int]) -> str:
        return self.model.tokenizer.decode(tokens, skip_special_tokens=True)

    def encode(self, texts: list[str], kind: str) -> list[list[float]]:
        if kind not in ("query", "passage"):
            raise ValueError("Unknown embedding prefix")
        prepared = [f"{kind}: {text.strip()}" for text in texts]
        if any(len(self.tokens(text)) > 500 for text in prepared):
            raise ValueError("Текст превышает контекст embedding-модели")
        vectors = np.asarray(
            self.model.encode(
                prepared, normalize_embeddings=True, batch_size=16, show_progress_bar=False
            )
        )
        if vectors.shape != (len(texts), 384) or not np.isfinite(vectors).all():
            raise ValueError("Некорректная размерность embeddings")
        return vectors.tolist()


provider = Embeddings()
