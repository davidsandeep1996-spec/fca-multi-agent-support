"""
RAG Service (API-Driven Enterprise Architecture)
Handles PDF ingestion, chunking, and semantic search using Hugging Face's Free API.
Optimized for low-memory environments (< 512MB RAM).
"""

import os
import logging
import re
from typing import List, Dict, Any
from sqlalchemy import Column, Integer, String, Text, select, func
from pgvector.sqlalchemy import Vector
import PyPDF2

from app.database import Base, AsyncSessionLocal

# 1. Import the official Async Client
from huggingface_hub import AsyncInferenceClient

logger = logging.getLogger(__name__)


class DocumentChunk(Base):
    """Stores document text chunks and their mathematical vector embeddings."""

    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String, index=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(384))


class RAGService:
    def __init__(self):
        # The model from your snippet
        self.model_name = "sentence-transformers/all-MiniLM-L6-v2"

        # 2. Initialize the client dynamically
        # It will automatically pick up the HF_TOKEN from your environment variables
        self.client = AsyncInferenceClient(token=os.environ.get("HF_TOKEN"))

    async def _get_embedding(self, text: str) -> List[float]:
        """
        Gets the vector embedding for a piece of text using the new InferenceClient.
        """
        try:
            # 3. Use feature_extraction to get the raw vector numbers for pgvector!
            embedding = await self.client.feature_extraction(
                text, model=self.model_name
            )

            # Ensure it is a flat Python list for SQLAlchemy
            if hasattr(embedding, "tolist"):
                embedding = embedding.tolist()

            # Sometimes the API wraps the vector in an outer list [[0.1, 0.2...]]
            if (
                isinstance(embedding, list)
                and len(embedding) > 0
                and isinstance(embedding[0], list)
            ):
                return embedding[0]

            return embedding

        except Exception as e:
            logger.error(f"Hugging Face API Error: {e}")
            # Safe fallback so the database transaction doesn't crash
            return [0.0] * 384

    def _chunk_text(self, text: str) -> List[str]:
        """Resilient Regex Chunking to handle messy PDF layouts."""
        clean_text = re.sub(r"\s+", " ", text).strip()
        raw_segments = re.split(r"\s*[Qq]\s*:\s*", clean_text)
        chunks = []
        for segment in raw_segments:
            seg = segment.strip()
            if not seg or len(seg) < 20:
                continue
            chunks.append(f"Q: {seg}")
        return chunks

    async def ingest_pdf(self, filepath: str) -> int:
        self.logger.info(f"Ingesting PDF: {filepath}")
        filename = os.path.basename(filepath)
        text = ""
        with open(filepath, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"

        chunks = self._chunk_text(text)
        async with AsyncSessionLocal() as session:
            for chunk_text in chunks:
                vector = await self._get_embedding(chunk_text)
                doc = DocumentChunk(
                    filename=filename, content=chunk_text, embedding=vector
                )
                session.add(doc)
            await session.commit()
        return len(chunks)

    async def search(self, query: str, limit: int = 15) -> List[Dict[str, Any]]:
        # ✅ Get query embedding from the API
        query_vector = await self._get_embedding(query)

        async with AsyncSessionLocal() as session:
            # 1. SEMANTIC SEARCH
            vector_stmt = (
                select(DocumentChunk)
                .order_by(DocumentChunk.embedding.l2_distance(query_vector))
                .limit(30)
            )
            v_result = await session.execute(vector_stmt)
            vector_results = v_result.scalars().all()

            # 2. LEXICAL SEARCH
            lexical_stmt = (
                select(DocumentChunk)
                .where(
                    func.to_tsvector("english", DocumentChunk.content).op("@@")(
                        func.websearch_to_tsquery("english", query)
                    )
                )
                .limit(30)
            )
            l_result = await session.execute(lexical_stmt)
            lexical_results = l_result.scalars().all()

        # 3. RECIPROCAL RANK FUSION (RRF) with Lexical Boost
        rrf_scores = {}
        k = 60

        for rank, res in enumerate(vector_results):
            rrf_scores[res.id] = rrf_scores.get(res.id, 0) + (1.0 / (k + rank + 1))

        for rank, res in enumerate(lexical_results):
            rrf_scores[res.id] = rrf_scores.get(res.id, 0) + (2.0 / (k + rank + 1))

        all_matches = {res.id: res for res in (vector_results + lexical_results)}
        sorted_ids = sorted(
            rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True
        )

        return [
            {
                "filename": all_matches[doc_id].filename,
                "content": all_matches[doc_id].content,
            }
            for doc_id in sorted_ids[:limit]
        ]
