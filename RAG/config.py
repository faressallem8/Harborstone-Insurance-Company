
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT /"harborstone_manual.txt"
CHROMA_PATH = PROJECT_ROOT / "chroma_db"

DEFAULT_RETRIEVER="naive"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Chunking
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# Retrieval
DEFAULT_TOP_K = 5

# Number of candidates pulled from EACH retriever (vector + BM25)
RETRIEVAL_CANDIDATE_K = 10

# Number of final chunks fed to the LLM after fusion
FUSION_FINAL_K = 5


GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")