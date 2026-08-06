
import numpy as np
from rank_bm25 import BM25Okapi
from RAG.vector_store import HarborstoneVectorStore
from RAG.config import GROQ_MODEL, RETRIEVAL_CANDIDATE_K, FUSION_FINAL_K, DEFAULT_TOP_K
from groq import Groq
import os
from dotenv import load_dotenv
load_dotenv()


llm = Groq(api_key=os.getenv("GROQ_API_KEY"))


class BaseRetriever:
    def __init__(self, vector_store: HarborstoneVectorStore):
        self.vector_store = vector_store
        self.model = GROQ_MODEL
        self.llm = llm

    def _generate(self, query: str, context: str) -> str:
        prompt = f"""You are an insurance assistant. Answer the question using ONLY the context below.
If the context doesn't contain the answer, say "I don't know."

Context:
{context}

Question: {query}
Answer:"""
        resp = self.llm.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return resp.choices[0].message.content


# --- 1. Naive RAG ---
class NaiveRAG(BaseRetriever):
    def answer(self, query: str):
        hits = self.vector_store.retrieve(query, top_k=DEFAULT_TOP_K)
        context = "\n\n".join([h["text"] for h in hits])
        answer = self._generate(query, context)
        return {"answer": answer, "sources": hits}


# --- 2. Hybrid RAG (Vector + BM25) ---
class HybridRAG(BaseRetriever):
    def __init__(self, vector_store: HarborstoneVectorStore):
        super().__init__(vector_store)
        self._build_bm25()

    def _build_bm25(self):

        all_docs = self.vector_store.collection.get()  # returns dict with 'documents'
        self.all_texts = all_docs.get("documents", [])
        tokenized_docs = [doc.lower().split() for doc in self.all_texts]
        self.bm25 = BM25Okapi(tokenized_docs)

    def _reciprocal_rank_fusion(self, vector_hits, bm25_hits, k=60):
        # Map text to score
        scores = {}
        for rank, item in enumerate(vector_hits):
            text = item["text"]
            scores[text] = scores.get(text, 0) + 1 / (k + rank + 1)
        for rank, item in enumerate(bm25_hits):
            text = item["text"]
            scores[text] = scores.get(text, 0) + 1 / (k + rank + 1)
        sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [{"text": text} for text, score in sorted_items]

    def answer(self, query: str):
        # 1. Vector top 10
        vector_hits = self.vector_store.retrieve(query, top_k=RETRIEVAL_CANDIDATE_K)

        # 2. BM25 top 10
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25.get_scores(tokenized_query)
        top_indices = np.argsort(bm25_scores)[-10:][::-1]
        bm25_hits = [{"text": self.all_texts[i]} for i in top_indices if bm25_scores[i] > 0]

        # 3. Fuse
        fused = self._reciprocal_rank_fusion(vector_hits, bm25_hits)
        context = "\n\n".join([f["text"] for f in fused[:FUSION_FINAL_K]])

        answer = self._generate(query, context)
        return {"answer": answer, "sources": fused[:5]}


# --- 3. Agentic RAG (Multi-hop) ---
class AgenticRAG(BaseRetriever):
    def _grade(self, query: str, chunk: str) -> bool:
        prompt = f"Is this context RELEVANT to the question? Answer Yes/No.\nQuestion: {query}\nContext: {chunk[:300]}"
        resp = self.llm.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return "yes" in resp.choices[0].message.content.lower()

    def _rewrite(self, query: str, missing: str) -> str:
        prompt = f"The question '{query}' needs specific info about {missing}. Write a new specific question to find this."
        resp = self.llm.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return resp.choices[0].message.content

    def answer(self, query: str, max_rounds=3):
        current_query = query
        all_sources = []

        for _ in range(max_rounds):
            hits = self.vector_store.retrieve(current_query, top_k=DEFAULT_TOP_K)
            all_sources.extend(hits)

            # Grade relevance
            relevant = [h for h in hits if self._grade(query, h["text"])]
            if len(relevant) >= 2:
                context = "\n\n".join([h["text"] for h in relevant])
                break
            else:

                current_query = self._rewrite(query, "specific policy details")
        else:
            # Fallback if loop finishes without break
            context = "\n\n".join([h["text"] for h in all_sources[:5]])

        answer = self._generate(query, context)
        return {"answer": answer, "sources": all_sources}