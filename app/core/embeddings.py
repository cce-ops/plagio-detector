from functools import lru_cache
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    # Se carga una sola vez en memoria
    return SentenceTransformer(MODEL_NAME)


def embed_texts(textos: list[str]) -> list[list[float]]:
    model = get_model()
    return model.encode(
        textos, normalize_embeddings=True, show_progress_bar=False
    ).tolist()