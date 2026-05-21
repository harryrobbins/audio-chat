# Kokoro-82M Podcast Generator 🎙️

A high-performance, multi-agent AI application that transforms raw documents into engaging two-person audio podcasts. Powered by **Google ADK**, **FastAPI**, **Kokoro-82M TTS**, and **Vue 3**.

## ✨ Key Features
- **Multi-Agent Orchestration:** Uses the official Google Agent Development Kit (ADK) with a native Sequential/Loop flow for iterative script refinement.
- **Incremental Knowledge Base:** Extracts core truths and summaries from your documents to build a persistent project wiki.
- **Fast, High-Quality TTS:** Generates ultra-realistic speech using the lightweight Kokoro-82M model (~80MB).
- **Persistent Backend:** Full SQLite/SQLAlchemy support for managing multiple podcast projects and document archives.
- **Modern UI:** Clean, accessible **GOV.UK-inspired** frontend built with Vue 3 and Tailwind CSS.
- **Full Observability:** Integrated with **Arize Phoenix** for deep-dive tracing of LLM calls, token usage, and agent interactions.

---

## 🚀 Getting Started

### 1. Prerequisites
- **Docker & Docker Compose**
- **Google Gemini API Key** (Set in `.env`)
- **espeak-ng** (Handled automatically in Docker)

### 2. Configuration
Create a `.env` file in the project root:
```text
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
PHOENIX_PROJECT_NAME=audio-chat
```

### 3. Launch the Environment
```bash
docker compose up -d --build
```
- **App UI:** `http://localhost:5173` (Frontend)
- **API Docs:** `http://localhost:8000/docs` (FastAPI Swagger)
- **Observability:** `http://localhost:3000` (Arize Phoenix)

---

## 🛠️ Project Architecture

### Backend (`/`)
- `main.py`: FastAPI server entry point with Lifespan management.
- `models.py` & `database.py`: Persistence layer (SQLite).
- `agents/`: Modular ADK agents (Fact Extraction, Persona Gen, Scriptwriting).
- `routers/`: API endpoints for Projects, Documents, and Podcast Flows.

### Frontend (`/frontend`)
- **Framework:** Vue 3 (Composition API) + Vite.
- **Styling:** Tailwind CSS with custom GOV.UK design tokens.
- **Real-time:** Server-Sent Events (SSE) for monitoring agent "thinking" process.

---

## 🧪 Testing

### End-to-End CLI Test
Run the full doc-to-audio journey from the terminal:
```bash
docker compose exec app uv run generate_final_podcast.py
```

### TTS Micro-test
```bash
docker compose exec app uv run test_client.py
```

---

## 📖 Documentation
- [Implementation Plan](IMPLEMENTATION_PLAN.md) - Project status and roadmap.
- [Agent Configuration](AGENTS.md) - Deep dive into ADK agent roles and flow.
- [Sample Text](sample-text-palestine-records.md) - A complex article used for verification.
