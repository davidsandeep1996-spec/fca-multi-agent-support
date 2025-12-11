# FCA Multi-Agent Support System

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104.1-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**FCA-compliant multi-agent AI support system for UK financial services.**

An intelligent customer support system using LangGraph multi-agent orchestration with FCA Consumer Duty compliance validation.

---

## ✨ Features

🤖 **Multi-Agent Architecture**
- Intent classification for smart routing
- Specialized agents (FAQ, Account, Payment, Compliance, Escalation)
- LangGraph workflow orchestration

🛡️ **FCA Consumer Duty Compliance**
- Automated compliance checking
- Vulnerable customer identification
- Fair treatment validation
- Clear communication standards

🚀 **Production-Ready**
- FastAPI async framework
- PostgreSQL database with SQLAlchemy ORM
- Redis caching (optional)
- Comprehensive testing
- Docker support

📊 **Monitoring & Audit**
- Complete audit trail
- Agent performance metrics
- Conversation analytics
- Request tracking

---

## 🏗️ Architecture

```
User → FastAPI → LangGraph Workflow
                      ↓
        ┌─────────────────────────┐
        │   Intent Classifier     │
        └───────────┬─────────────┘
                    ↓
        ┌───────────────────────────────┐
        │  FAQ | Account | Payment      │
        └───────────┬───────────────────┘
                    ↓
        ┌───────────────────────────┐
        │   Compliance Checker      │
        └───────────┬───────────────┘
                    ↓
        ┌───────────────────────────┐
        │   Escalation Agent        │
        └───────────────────────────┘
```

---

## 📋 Prerequisites

- **Python 3.11+**
- **PostgreSQL 15+**
- **Docker** (optional, recommended)
- **Groq API Key** (free at https://console.groq.com)

---

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/fca-multi-agent-support.git
cd fca-multi-agent-support
```

### 2. Set Up Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment Variables

```bash
# Copy template
cp .env.example .env

# Edit .env with your settings
# REQUIRED: Add your Groq API key
notepad .env  # Windows
nano .env     # Mac/Linux
```

### 4. Start Database (Docker)

```bash
docker-compose up -d db redis
```

### 5. Initialize Database

```bash
python scripts/init_db.py create
```

### 6. Run Application

```bash
uvicorn app.main:app --reload
```

Visit: http://localhost:8000/docs

---

## 📁 Project Structure

```
fca-multi-agent-support/
├── app/
│   ├── agents/          # AI agent implementations
│   ├── graph/           # LangGraph workflows
│   ├── models/          # Database models
│   ├── routers/         # API endpoints
│   ├── services/        # Business logic
│   ├── middleware/      # HTTP middleware
│   ├── config.py        # Configuration
│   ├── database.py      # Database setup
│   ├── logger.py        # Logging
│   └── main.py          # FastAPI app
│
├── tests/               # Test suite
├── docs/                # Documentation
├── scripts/             # Utility scripts
├── .github/workflows/   # CI/CD pipelines
│
├── docker-compose.yml   # Docker orchestration
├── Dockerfile           # Container definition
├── requirements.txt     # Python dependencies
├── pyproject.toml       # Tool configuration
├── .env.example         # Environment template
└── README.md            # This file
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_agents.py

# Run integration tests only
pytest -m integration
```

---

## 🐳 Docker

### Using Docker Compose (Recommended)

```bash
# Start all services (app, database, redis)
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build
```

### Manual Docker Build

```bash
# Build image
docker build -t fca-support .

# Run container
docker run -p 8000:8000 --env-file .env fca-support
```

---

## 📊 API Endpoints

### Chat
- `POST /api/v1/chat` - Send message and get response
- `GET /api/v1/conversation/{id}` - Get conversation history

### Health
- `GET /api/v1/health` - System health check
- `GET /api/v1/ping` - Simple ping

### Documentation
- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc UI

---

## 🔧 Development

### Code Formatting

```bash
# Format code with black
black app/

# Sort imports
isort app/

# Lint with flake8
flake8 app/

# Type checking
mypy app/
```

### Database Migrations

```bash
# Create migration
alembic revision -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## 📈 Monitoring

### Logs

Logs are written to `logs/app.log` in JSON format:

```bash
# View logs
tail -f logs/app.log

# Parse JSON logs
cat logs/app.log | jq
```

### Metrics

Agent performance metrics tracked in `agent_metrics` table.

---

## 🛡️ Security

- ✅ Environment variables for secrets
- ✅ SQL injection prevention (SQLAlchemy ORM)
- ✅ Input validation (Pydantic)
- ✅ Rate limiting
- ✅ CORS configuration
- ✅ Request size limits

---

## 📝 Configuration

Key environment variables (see `.env.example`):

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq AI API key | ✅ Yes |
| `DATABASE_URL` | PostgreSQL connection | ✅ Yes |
| `SECRET_KEY` | Encryption key | ✅ Yes |
| `REDIS_URL` | Redis connection | ❌ Optional |
| `LOG_LEVEL` | Logging verbosity | ❌ Optional |

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Code Standards

- Follow PEP 8 (enforced by black)
- Add tests for new features
- Update documentation
- Keep commits atomic

---

## 📜 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file.

---

## 🙏 Acknowledgments

- **LangChain & LangGraph** - AI agent framework
- **FastAPI** - Web framework
- **Groq** - Fast LLM inference
- **FCA** - Consumer Duty principles

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/davidsandeep1996-spec/fca-multi-agent-support/issues)

- **Email**: davidsandeep1996@gmail.com

---

## 🗺️ Roadmap

- [x] Phase 1: Project setup
- [x] Phase 2: Core application
- [x] Phase 3: Database layer
- [x] Phase 4: Multi-agent system
- [x] Phase 5: API & services
- [ ] Phase 6: WebSocket support
- [ ] Phase 7: Admin dashboard
- [ ] Phase 8: Production deployment


## Progress

### ✅ Phase 1: Project Setup (Complete)
- Git repository initialized
- Directory structure created
- Configuration files (.gitignore, .env.example, etc.)
- Docker setup (Dockerfile, docker-compose.yml)
- CI/CD pipeline (.github/workflows/ci.yml)
- Development environment (VS Code settings)
- Documentation (README, CONTRIBUTING, Architecture)

### ✅ Phase 2: Core Application (Complete)
- FastAPI application structure
- Configuration management (Pydantic Settings)
- Structured logging (JSON format)
- Database connection (SQLAlchemy async)
- Base models and mixins
- Health check endpoints
- Test infrastructure (pytest)
- Basic test coverage

### 🔄 Phase 3: Database Layer (In Progress)
- Customer model
- Conversation model
- Message model
- Repository pattern
- Service layer

### ⏳ Phase 4: Multi-Agent System
- Agent base classes
- Intent classifier
- Product recommender
- Compliance checker
- LangGraph workflow

### ⏳ Phase 5: API & Services
- Conversation endpoints
- Message endpoints
- WebSocket support
- Real-time chat

---

**Made with ❤️ for UK Financial Services**
