"""
RAG Service (Retrieval-Augmented Generation)
Handles PDF ingestion, chunking, local embedding, and vector search.
"""
import os
import logging
from typing import List, Dict, Any
from sqlalchemy import Column, Integer, String, Text, select
from pgvector.sqlalchemy import Vector
from sentence_transformers import SentenceTransformer
import PyPDF2

from app.database import Base, AsyncSessionLocal

logger = logging.getLogger(__name__)

# ============================================================================
# 4a. DATABASE MODEL FOR RAG
# ============================================================================
class DocumentChunk(Base):
    """Stores document text chunks and their mathematical vector embeddings."""
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, index=True)
    content = Column(Text, nullable=False)
    # 384 dimensions matches the 'all-MiniLM-L6-v2' model output
    embedding = Column(Vector(384))


# ============================================================================
# 4b. RAG PIPELINE SERVICE
# ============================================================================
class RAGService:
    def __init__(self):
        # Loads a fast, local embedding model (downloads ~80MB on first run)
        self.logger = logging.getLogger(__name__)
        self.logger.info("Loading local embedding model (all-MiniLM-L6-v2)...")
        self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def _chunk_text(self, text: str, chunk_size: int = 2000, overlap: int = 0) -> List[str]:
        """
        Semantic Q&A Chunking with Cleaning.
        1. Cleans newlines (turns '90\ndays' into '90 days').
        2. Splits by 'Q:' to keep Questions and Answers together.
        """
        # [CRITICAL FIX] Remove newlines that break matching
        clean_text = text.replace("\n", " ").replace("  ", " ")

        chunks = []
        # Split by "Q:" to get natural semantic blocks
        raw_segments = clean_text.split("Q:")

        for segment in raw_segments:
            seg = segment.strip()
            if not seg or len(seg) < 10: continue # Skip empty/tiny chunks

            # Reconstruct the Q&A pair
            # We prepend "Q: " so the LLM knows it's a question
            full_chunk = f"Q: {seg}"
            chunks.append(full_chunk)

        return chunks

    async def ingest_pdf(self, filepath: str) -> int:
        self.logger.info(f"Ingesting PDF: {filepath}")
        filename = os.path.basename(filepath)

        text = ""
        with open(filepath, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + " " # Add space, not newline

        chunks = self._chunk_text(text)

        async with AsyncSessionLocal() as session:
            for chunk_text in chunks:
                vector = self.model.encode(chunk_text).tolist()
                doc = DocumentChunk(filename=filename, content=chunk_text, embedding=vector)
                session.add(doc)
            await session.commit()

        return len(chunks)

    

    async def search(self, query: str, limit: int = 6) -> List[Dict[str, Any]]:
        """Finds the most relevant document chunks for a given user query."""
        # 1. Convert the user's question into a vector
        query_vector = self.model.encode(query).tolist()

        # 2. Ask pgvector to find the closest matches using L2 distance (<->)
        async with AsyncSessionLocal() as session:
            stmt = select(DocumentChunk).order_by(
                DocumentChunk.embedding.l2_distance(query_vector)
            ).limit(limit)

            result = await session.execute(stmt)
            chunks = result.scalars().all()

            return [
                {"filename": c.filename, "content": c.content}
                for c in chunks
            ]
