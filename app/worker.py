import os
import asyncio
from celery import Celery
from app.services.rag_service import RAGService

# [CHANGE 2a] Define Celery App
celery_app = Celery(
    "fca_worker",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
)

# [CHANGE 2b] Define Background Task
@celery_app.task(name="ingest_pdf_task")
def ingest_pdf_task(file_path: str):
    """
    Background task to ingest a PDF.
    Wraps the async RAGService in a sync Celery task.
    """
    print(f"🚀 [Worker] Starting background ingestion for: {file_path}")

    async def _run_ingest():
        # Initialize Service (DB connection is handled internally)
        service = RAGService()
        # Assume ingest_pdf takes a file path string
        # You might need to adjust RAGService to accept a path if it currently takes a file object
        count = await service.ingest_pdf(file_path)
        return count

    try:
        # Run the async code synchronously
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        chunks_count = loop.run_until_complete(_run_ingest())
        print(f"✅ [Worker] Ingestion complete. Chunks: {chunks_count}")
        return {"status": "success", "chunks": chunks_count}
    except Exception as e:
        print(f"❌ [Worker] Ingestion failed: {e}")
        return {"status": "error", "message": str(e)}
