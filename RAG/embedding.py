
from sentence_transformers import SentenceTransformer
from RAG.config import EMBEDDING_MODEL


_encoder = SentenceTransformer(EMBEDDING_MODEL)

def embed_texts(texts: list[str]) -> list[list[float]]:
    return _encoder.encode(texts, convert_to_numpy=True).tolist()

def embed_query(query: str) -> list[float]:
    return _encoder.encode([query], convert_to_numpy=True).tolist()[0]