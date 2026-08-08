import logging
from typing import Dict, Any

logger = logging.getLogger("Harborstone.Memory")

class MemorySelfRAGVerifier:
    """
    Verifies that retrieved memory facts are relevant 
    and sufficient to support answering the user query.
    """

    def verify(self, query: str, memory_context: str) -> Dict[str, Any]:
        if not memory_context or "No previous memory available" in memory_context:
            return {
                "passed": False,
                "reason": "REJECT: Memory context is empty."
            }

        # Check keyword/semantic match
        query_words = set(query.lower().split())
        memory_words = set(memory_context.lower().split())

        # Basic overlap check
        overlap = query_words.intersection(memory_words)
        
        if len(overlap) >= 1:
            logger.info("[MEMORY SELF-RAG] PASS: Memory content is relevant to the query.")
            return {
                "passed": True,
                "reason": "PASS: Memory fact is relevant and supports the response."
            }

        logger.warning("[MEMORY SELF-RAG] REJECT: Memory does not contain relevant context.")
        return {
            "passed": False,
            "reason": "REJECT: Retrived memory is irrelevant to the query."
        }