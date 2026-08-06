# rag/self_rag.py
from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

class SelfRAGVerifier:
    def __init__(self):
        self.llm = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    def verify(self, question: str, answer: str, sources: list) -> dict:
        if not sources:
            return {"passed": False, "reason": "No sources retrieved."}

        # 1. Check if answer is supported (Faithfulness)
        context = "\n".join([s["text"][:500] for s in sources[:2]])
        prompt_support = f"""Does the answer strictly follow from the context? Answer Yes/No.
Context: {context}
Answer: {answer}"""
        resp = self.llm.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt_support}],
            temperature=0
        )
        is_supported = "yes" in resp.choices[0].message.content.lower()

        # 2. Check if answer is relevant (answer directly addresses question)
        prompt_relevance = f"Is this answer relevant to the question? Answer Yes/No.\nQuestion: {question}\nAnswer: {answer}"
        resp = self.llm.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt_relevance}],
            temperature=0)
        is_relevant = "yes" in resp.choices[0].message.content.lower()

        passed = is_supported and is_relevant
        return {
            "passed": passed,
            "supported": is_supported,
            "relevant": is_relevant,
            "reason": f"Supported: {is_supported}, Relevant: {is_relevant}"
        }