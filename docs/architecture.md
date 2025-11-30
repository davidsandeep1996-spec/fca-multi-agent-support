# System Architecture

## Overview

The FCA Multi-Agent Support System is a production-ready AI customer support application built for UK financial services. It uses a multi-agent architecture with LangGraph orchestration to provide compliant, intelligent responses.

## High-Level Architecture

```
┌─────────────┐
│   Client    │
│  (Browser)  │
└──────┬──────┘
       │ HTTP/HTTPS
       ↓
┌─────────────────────────────────────────┐
│           FastAPI Application            │
│  ┌────────────────────────────────────┐ │
│  │         API Layer (Routers)        │ │
│  └────────────┬───────────────────────┘ │
│               ↓                          │
│  ┌────────────────────────────────────┐ │
│  │      Service Layer (Business)      │ │
│  └────────────┬───────────────────────┘ │
│               ↓                          │
│  ┌────────────────────────────────────┐ │
│  │    LangGraph Workflow Engine       │ │
│  │  ┌──────────────────────────────┐  │ │
│  │  │    Multi-Agent System        │  │ │
│  │  │  • Intent Classifier         │  │ │
│  │  │  • FAQ Retriever             │  │ │
│  │  │  • Account Lookup            │  │ │
│  │  │  • Payment Handler           │  │ │
│  │  │  • Compliance Checker        │  │ │
│  │  │  • Escalation Agent          │  │ │
│  │  └──────────────────────────────┘  │ │
│  └────────────┬───────────────────────┘ │
│               ↓                          │
│  ┌────────────────────────────────────┐ │
│  │      Database Layer (ORM)          │ │
│  └────────────┬───────────────────────┘ │
└───────────────┼─────────────────────────┘
                ↓
┌───────────────┴───────────────┐
│  ┌─────────────┐  ┌─────────┐ │
│  │ PostgreSQL  │  │  Redis  │ │
│  │  Database   │  │  Cache  │ │
│  └─────────────┘  └─────────┘ │
└───────────────────────────────┘
       │                  │
       ↓                  ↓
   Persistent         In-Memory
     Storage          Storage
```

## Component Details

### API Layer
- **FastAPI Routers** - HTTP endpoint definitions
- **Pydantic Models** - Request/response validation
- **Middleware** - Cross-cutting concerns (logging, CORS, rate limiting)

### Service Layer
- **ConversationService** - Orchestrates agent workflow
- **HealthService** - System health monitoring

### LangGraph Workflow
- **State Machine** - Defines conversation flow
- **Agent Routing** - Routes messages to appropriate agents
- **Error Handling** - Graceful degradation

### Database Layer
- **SQLAlchemy ORM** - Object-relational mapping
- **Async Support** - Non-blocking database operations
- **Alembic Migrations** - Database version control

### External Services
- **Groq AI API** - LLM inference
- **PostgreSQL** - Persistent data storage
- **Redis** - Caching layer

## Data Flow

1. **User sends message** → FastAPI receives HTTP request
2. **Request validation** → Pydantic validates input
3. **Service layer** → ConversationService handles request
4. **Database lookup** → Fetch customer/conversation
5. **LangGraph workflow** → Execute agent pipeline
6. **Agent processing** → Each agent processes in sequence
7. **Database save** → Store results
8. **Response** → Return to user

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Web Framework** | FastAPI | 0.104.1 | API endpoints |
| **ASGI Server** | Uvicorn | 0.24.0 | HTTP server |
| **Database** | PostgreSQL | 15 | Persistent storage |
| **ORM** | SQLAlchemy | 2.0.23 | Database abstraction |
| **Cache** | Redis | 7 | In-memory cache |
| **AI Framework** | LangChain | 0.1.0 | LLM orchestration |
| **Workflow** | LangGraph | 0.0.20 | Agent routing |
| **LLM Provider** | Groq AI | - | Fast inference |
| **Testing** | pytest | 7.4.3 | Test framework |
| **Containerization** | Docker | - | Deployment |

## Design Patterns

### Multi-Agent Pattern
Each agent specializes in one task:
- **Single Responsibility** - One agent, one purpose
- **Composability** - Agents combine flexibly
- **Testability** - Test agents independently

### Service Layer Pattern
Separates business logic from API:
- **Reusability** - Services used by multiple endpoints
- **Testability** - Test services without HTTP
- **Maintainability** - Change business logic independently

### Repository Pattern
Database abstraction:
- **Abstraction** - Hide database details
- **Testability** - Mock database easily
- **Flexibility** - Switch databases if needed

## Security Considerations

- ✅ Environment variables for secrets
- ✅ Non-root Docker user
- ✅ Input validation (Pydantic)
- ✅ SQL injection prevention (ORM)
- ✅ Rate limiting
- ✅ CORS configuration
- ✅ Request size limits
- ✅ Audit logging

## Scalability

### Horizontal Scaling
- Stateless application (scale containers)
- Database connection pooling
- Redis for shared state

### Performance Optimizations
- Async I/O (FastAPI + asyncpg)
- Database indexes
- Redis caching
- Connection pooling

## Deployment Architecture

```
Internet
   ↓
Load Balancer
   ↓
┌─────────┬─────────┬─────────┐
│ App 1   │ App 2   │ App 3   │  (Docker containers)
└────┬────┴────┬────┴────┬────┘
     └─────────┴─────────┘
            ↓
     ┌────────────┐
     │ PostgreSQL │
     │  (Primary) │
     └────────────┘
```

## Future Enhancements

- [ ] WebSocket support for real-time chat
- [ ] Admin dashboard
- [ ] Advanced analytics
- [ ] Kubernetes deployment
- [ ] Multi-region support
- [ ] Vector database for semantic search
