import asyncio
import os
import sys

# Ensure we can import from the 'app' folder
sys.path.append(os.getcwd())

from app.services.rag_service import RAGService

async def run_ingestion():
    print("🚀 Starting RAG Ingestion...")
    rag = RAGService()

    # Updated to match the file you actually uploaded
    pdf_path = "data/FCA faqs.pdf"

    if not os.path.exists(pdf_path):
        print(f"❌ Error: File not found at {pdf_path}")
        print("   Make sure you saved the PDF inside a 'data' folder in your project root.")
        return

    try:
        chunks = await rag.ingest_pdf(pdf_path)
        print(f"✅ SUCCESS! Ingested {chunks} document chunks into pgvector.")
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    asyncio.run(run_ingestion())
