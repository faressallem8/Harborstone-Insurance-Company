
from langchain_text_splitters import RecursiveCharacterTextSplitter
from RAG.config import CHUNK_SIZE, CHUNK_OVERLAP

def chunk_document(text: str):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)