# FCA Multi-Agent Support System

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)  
[![FastAPI](https://img.shields.io/badge/FastAPI-0.128.0-green.svg)](https://fastapi.tiangolo.com/)  
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An intelligent, production-ready customer support system designed for UK financial services.  
It uses a **LangGraph-based multi-agent architecture** with strict **FCA Consumer Duty compliance validation**, PII redaction, and prompt-injection defense.

---

# ✨ Features

## 🤖 Multi-Agent Orchestration (LangGraph)

- Intent classification routes queries to specialized agents  
- Dedicated agents:
  - Account inquiries
  - FAQ / RAG knowledge
  - Product recommendations
  - Human escalation
- Stateful conversation memory via `AgentCoordinator`

---

## 🛡️ FCA Compliance & Security

**Compliance Agent**
- Detects prohibited claims (e.g., “risk-free”)  
- Appends mandatory FCA disclaimers  
- Blocks non-compliant responses  

**Security Guardrails**
- Prompt-injection defense (Lakera Guard)  
- PII detection & redaction (Microsoft Presidio)  

---

## 🚀 High-Performance Backend

- FastAPI async API  
- PostgreSQL + pgvector (relational + vector search)  
- Redis + Celery (cache & background tasks)  
- SQLAlchemy async ORM  

---

## 📊 Observability & Metrics

- Langfuse (LLM tracing)  
- Prometheus (metrics)  
- Structured JSON logging  

---

# 🏗️ System Architecture

The platform uses a LangGraph state machine to safely process messages:

```text
User Input
   ↓
Security Guardrail (Lakera Guard + Presidio)
   ↓
Intent Classifier Agent
   ↓
 ┌───────────────┬───────────────┬───────────────┐
 ↓               ↓               ↓
Account       General (RAG)    Product
Agent          Agent           Agent
 │               │               ↓
 │               │        Compliance Checker
 │               │               ↓
 └───────────────┴───────────────→ Response
```

Sensitive or complaint-related messages are automatically routed to the **Human Agent**.

---

# 💻 Tech Stack

**Core**  
- Python 3.11  
- FastAPI  
- Uvicorn  
- Pydantic  

**AI / LLM**  
- Groq API (mixtral-8x7b-32768)  
- LangChain  
- LangGraph  

**Database**  
- PostgreSQL 15  
- pgvector  
- SQLAlchemy (async)  
- Alembic  

**Vector Embeddings**  
- sentence-transformers (all-MiniLM-L6-v2)  
- PyPDF2  

**Task Queue**  
- Celery  
- Redis  

**Security**  
- Microsoft Presidio  
- Lakera Guard  
- passlib  
- python-jose (JWT)  

**Monitoring**  
- Langfuse  
- Prometheus Instrumentator  

**Testing**  
- Pytest  
- pytest-asyncio  
- httpx  

---

# 📁 Project Structure

```text
fca-multi-agent-support/
│
├── app/
│   ├── agents/          # AI agents (Account, General, Product, Compliance, Human, Intent)
│   ├── api/             # API routes & dependencies
│   ├── coordinator/     # Conversation state & memory manager
│   ├── models/          # SQLAlchemy DB models
│   ├── repositories/    # Database CRUD layer
│   ├── routers/         # FastAPI routers
│   ├── schemas/         # Pydantic schemas & workflow states
│   ├── services/        # Business logic (RAG, Security, Customer, Product)
│   ├── workflows/       # LangGraph state machine
│   ├── config.py        # Environment config
│   ├── database.py      # DB engine & session
│   ├── main.py          # FastAPI entrypoint
│   ├── seed_database.py # Test data generator
│   └── worker.py        # Celery worker
│
├── data/                # Source docs (PDFs, FAQs)
├── docs/                # Architecture docs
├── frontend/            # Streamlit UI
├── tests/               # Pytest suite
│
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

---

# 🚀 Quick Start (Docker)

Run the full stack (API, DB, Redis, Worker, Frontend) using Docker Compose.

## 1️⃣ Setup Environment

```bash
git clone <repository_url>
cd fca-multi-agent-support

cp .env.example .env
```

Required `.env` keys:

```
GROQ_API_KEY=
SECRET_KEY=
```

Optional:

```
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LAKERA_GUARD_API_KEY=
```

---

## 2️⃣ Start Services

```bash
docker-compose up -d --build
```

---

## 3️⃣ Initialize & Seed Database

```bash
docker-compose exec web python -m app.seed_database --clear --customers 100
```

---

## 4️⃣ Background Data Ingestion (RAG)

```bash
docker-compose exec web python -m app.ingest
```

---

## 5️⃣ Access the Application

- API docs → http://localhost:8000/docs  
- Streamlit UI → http://localhost:8501  

---

# 🧩 Core Components

## Agents (`app/agents/`)

**IntentClassifierAgent**  
Routes requests: account, product, FAQ, or human support.

**GeneralAgent**  
RAG-based FAQ & policy responses using pgvector.

**AccountAgent**  
Secure balance & transaction retrieval.

**ProductRecommenderAgent**  
Suggests savings, credit, or loan products.

**ComplianceCheckerAgent**  
Enforces FCA wording & disclaimers.

**HumanAgent**  
Creates escalation tickets with priority levels.

---

## LangGraph Workflow (`app/workflows/message_workflow.py`)

State machine controlling:

1. Guardrail validation  
2. Intent classification  
3. Agent routing  
4. Compliance check  
5. Response formatting  

---

## Security & PII (`app/services/security_service.py`)

**Prompt Injection Defense**
- Heuristic detection  
- Optional Lakera Guard API  

**PII Redaction**
- Presidio analyzer + anonymizer  
- Masks sensitive entities (e.g., card numbers)  

---

# 🧪 Testing & Verification

Run full test suite:

```bash
python verify_full_workflow.py
python verify_evaluation.py
python verify_memory.py
```

Diagnostic scripts:

- `verify_full_workflow.py` → end-to-end LangGraph test  
- `verify_rag.py` → semantic search evaluation  
- `verify_evaluation.py` → adversarial prompt testing  
- `verify_memory.py` → multi-turn context validation  

---

# 📡 API Highlights

**POST** `/api/v1/messages/process`  
Main chat endpoint.

**GET** `/chat/stream`  
Server-sent events streaming.

**POST** `/api/v1/admin/seed-db`  
Trigger DB seeding.

**POST** `/api/v1/admin/upload-background`  
Async PDF ingestion.

**GET** `/api/v1/health`  
System health diagnostics.

---

## 📜 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file.
