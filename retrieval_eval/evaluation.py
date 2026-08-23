
import time
from RAG.vector_store import HarborstoneVectorStore
from RAG.retriever import NaiveRAG, HybridRAG, AgenticRAG
from retrieval_eval.test import QUESTIONS
from RAG.config import DATA_PATH
store = HarborstoneVectorStore()

if len(store.collection.get()["ids"]) == 0:
    print("Vector store is empty. Indexing the manual...")
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        manual_text = f.read()
    store.index_document(manual_text, source="manual")
    print("Indexing complete.\n")

naive = NaiveRAG(store)
hybrid = HybridRAG(store)
agentic = AgenticRAG(store)


def evaluate(rag_instance, name):
    correct = 0
    total_tokens = 0
    total_latency = 0
    for q in QUESTIONS:
        start = time.time()
        res = rag_instance.answer(q["text"])
        latency = time.time() - start
        total_latency += latency

        # Token count rough
        total_tokens += len(res["answer"].split()) + sum(len(s["text"].split()) for s in res["sources"])

        # Check accuracy (keyword match)
        if q["expected_keyword"].lower() in res["answer"].lower():
            correct += 1
    return correct, total_tokens / len(QUESTIONS), total_latency / len(QUESTIONS)


# Run and print Markdown table
print("| Architecture | Accuracy | Avg Tokens | Avg Latency |")
print("|--------------|----------|------------|-------------|")
for name, cls in [("Naive", naive), ("Hybrid", hybrid), ("Agentic", agentic)]:
    acc, tok, lat = evaluate(cls, name)
    print(f"| {name} | {acc}/12 | {tok:.0f} | {lat:.2f}s |")