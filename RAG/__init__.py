# RAG/__init__.py
from RAG.vector_store import HarborstoneVectorStore
from RAG.retriever import NaiveRAG, HybridRAG, AgenticRAG
from RAG.self_rag import SelfRAGVerifier
from RAG.config import DEFAULT_RETRIEVER, DATA_PATH


def get_retriever(mode: str = DEFAULT_RETRIEVER):
    store = HarborstoneVectorStore()
    # Auto-index if empty (same logic as evaluation)
    if len(store.collection.get()["ids"]) == 0:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            store.index_document(f.read(), source="manual")

    if mode == "naive":
        return NaiveRAG(store)
    elif mode == "hybrid":
        return HybridRAG(store)
    elif mode == "agentic":
        return AgenticRAG(store)
    else:
        raise ValueError(f"Unknown retriever mode: {mode}")