
import chromadb
from chromadb.config import Settings
from typing import Optional, Dict, List
from RAG.config import CHROMA_PATH , DEFAULT_TOP_K
from RAG.chunking import chunk_document
from RAG.embedding import embed_texts, embed_query


class HarborstoneVectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_PATH),
            settings=Settings(anonymized_telemetry=False)
        )

        self.collection = self.client.get_or_create_collection(
            name="harborstone_docs",
            metadata={"hnsw:space": "cosine"}
        )

    def index_document(self, text: str, source: str = "manual"):
        """Chunk, embed, and store."""
        chunks = chunk_document(text)
        ids = [f"{source}_{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": source, "chunk_index": i, "total_chunks": len(chunks)}
            for i in range(len(chunks))
        ]
        embeddings = embed_texts(chunks)

        self.collection.add(
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Indexed {len(chunks)} chunks from {source}")

    def retrieve(self, query: str, top_k: int = DEFAULT_TOP_K, filters: Optional[Dict] = None) -> List[Dict]:
        """Retrieve chunks with optional metadata filtering."""
        q_vec = embed_query(query)
        results = self.collection.query(
            query_embeddings=[q_vec],
            n_results=top_k,
            where=filters,  # e.g., {"source": "manual"}
            include=["documents", "metadatas", "distances"]
        )

        return [
            {
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
                "similarity": 1.0 - results["distances"][0][i]  # crude conversion
            }
            for i in range(len(results["documents"][0]))
        ]