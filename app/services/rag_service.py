"""
RAG Service (API-Driven Enterprise Architecture)
Handles PDF ingestion, chunking, and semantic search using Hugging Face's Free API.
Optimized for low-memory environments (< 512MB RAM).
"""

import os
import logging
import re
import httpx
from typing import List, Dict, Any
from sqlalchemy import Column, Integer, String, Text, select, func
from pgvector.sqlalchemy import Vector
import PyPDF2

from app.database import Base, AsyncSessionLocal
from app.config import settings

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
        self.logger = logging.getLogger(__name__)
        # ✅ Using the exact same model via API so existing DB vectors don't break!
        self.hf_api_url = "https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2"

        # We will pull the HF token from settings
        self.hf_token = getattr(settings, "hf_token", None)
        if not self.hf_token:
            self.logger.warning("No HF_TOKEN found! Embeddings will fail unless provided.")

    async def _get_embedding(self, text: str) -> List[float]:
        """Fetches a 384-dimensional vector from Hugging Face's Free API."""
        headers = {"Authorization": f"Bearer {self.hf_token}"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.hf_api_url,
                    headers=headers,
                    json={"inputs": text},
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json() # Returns the List[float]
            except Exception as e:
                self.logger.error(f"Hugging Face API Error: {e}")
                # Fallback to prevent complete system crash (returns a zero-vector)
                return [0.0] * 384

    def _chunk_text(self, text: str) -> List[str]:
        """Resilient Regex Chunking to handle messy PDF layouts."""
        clean_text = re.sub(r'\s+', ' ', text).strip()
        raw_segments = re.split(r'\s*[Qq]\s*:\s*', clean_text)
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
                # ✅ Now calls the API instead of a local PyTorch model
                vector = await self._get_embedding(chunk_text)
                doc = DocumentChunk(filename=filename, content=chunk_text, embedding=vector)
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
                    func.to_tsvector('english', DocumentChunk.content).op('@@')(
                        func.websearch_to_tsquery('english', query)
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
        sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

        return [{"filename": all_matches[doc_id].filename, "content": all_matches[doc_id].content} for doc_id in sorted_ids[:limit]]
