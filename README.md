# QueryPilot: Stateful, Cyclic Text-to-SQL Agent Web Application

QueryPilot is a production-ready, deployable web application that transforms natural language questions into safe, optimized SQL queries using a stateful, cyclic agent workflow built on **LangGraph**.

The system supports a default e-commerce dataset (demo database mode) and allows users to upload custom datasets (CSV/XLSX), dynamically inspect inferred schemas, ask relational queries against isolated custom tables, and supply their own API keys (BYOK) securely.

---

## 🏗️ System Architecture

```
                                +-----------------------------------+
                                |            React UI               |
                                |       (Vite Client Server)        |
                                +-----------------+-----------------+
                                                  | (REST API / CORS)
                                                  v
                                +-----------------+-----------------+
                                |         FastAPI Backend           |
                                |     (Endpoints & Services)        |
                                +-----------------+-----------------+
                                                  |
                        +-------------------------+-------------------------+
                        |                                                   |
                        v (Demo Mode)                                       v (Custom Dataset Mode)
              +---------+---------+                               +---------+---------+
              |    Demo Dataset   |                               |  Isolated User Table |
              |  (E-Commerce DB)  |                               |   (dataset_uuid)  |
              +-------------------+                               +-------------------+
```

The Text-to-SQL engine runs a stateful 7-layer workflow:

1. **Prompt Analysis:** Classifies queries for ambiguity or out-of-domain scope dynamically.
2. **Clarification Node:** Halts execution (using LangGraph interrupts) if the question is ambiguous, requesting user input.
3. **Schema Retrieval (RAG):** Cosine vector similarity on `gemini-embedding-001` fetches the top 3 relevant tables for demo mode. Custom dataset mode loads the dynamic table DDL schema directly.
4. **SQL Generation:** Generates read-only PostgreSQL statements using schema DDL context.
5. **SQL Validation:** Performs static regex safety validation and dynamic `EXPLAIN` query compilations.
6. **Database Execution:** Executes validated SELECT statements against the target tables using `psycopg`.
7. **Answer Synthesis:** Explains query output rows in a natural, business-focused response.

---

## 🛠️ Tech Stack

* **Frontend:** React 18, Vite, Vanilla CSS (Glassmorphism layout, responsive cards, loader animations).
* **Backend:** FastAPI, Uvicorn, Python 3.12.
* **Orchestration & State:** LangGraph (checkpoints, interrupts, and transient config context).
* **LLM Gateway:** LiteLLM (`gemini/gemini-3.5-flash` model, backoff quota retries).
* **Database:** PostgreSQL, Psycopg 3 (v3 driver).
* **Utilities:** Pydantic (JSON bindings), OpenPyXL (Excel parsing), Dotenv (environments).
* **Testing:** Pytest, FastAPI TestClient.

---

## 🔒 Security Measures & Key Management

* **BYOK Scoped Keys:** User-provided API keys are request-scoped. They are kept in memory and passed in the headers of calls. They are **never** stored in the database, logged in telemetry, printed to files, or committed.
* **Graph Key Propagation:** The key is passed via the LangGraph `RunnableConfig` (`configurable` dictionary). Checkpointers (`MemorySaver`) do not serialize this transient configuration, keeping the key completely isolated from logs.
* **SQL Injection & DDL Blockers:** Static guardrails block write keywords (`DROP`, `DELETE`, `ALTER`, `TRUNCATE`, etc.), multiple statement semicolons, and restrict queries *strictly* to authorized tables.
* **Dataset Session Isolation:** Uploaded custom files are seeded into tables named `dataset_<uuid>`. Column headers are sanitized into safe SQL identifiers. A secure, anonymous session cookie (`querypilot_session`) associates datasets with specific browsers, preventing cross-tenant access.

---

## 🛜 REST API Endpoints

### Health Check

* `GET /health`: Returns health status.

### Custom Datasets

* `POST /api/datasets/upload`: Accepts CSV/XLSX files, validates sizes (<10MB), infers datatypes, creates tables, and bulk inserts data.
* `GET /api/datasets/{dataset_id}/schema`: Retrieves dynamic DDL mapping for prompts and UI explorers.
* `DELETE /api/datasets/{dataset_id}`: Drops the table and metadata.

### Query Engine

* `POST /api/query`: Submits natural language questions for both demo and custom dataset modes.
* `POST /api/query/resume`: Resumes a paused clarification interrupt thread.

---

## ⚙️ Setup & Run Instructions

### 1. Prerequisites

* Python 3.12
* Node.js (v18+)
* PostgreSQL running locally or in Docker.

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```env
# Database Credentials
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_NAME=querypilot

# Default Gemini API Key (Fallback if user does not provide key)
GEMINI_API_KEY=AIzaSy...

# CORS configuration (comma separated origins for production)
CORS_ORIGINS=http://localhost:5173
```

### 3. Initialize PostgreSQL Database

Seed the e-commerce demo dataset:

```bash
python database/setup_db.py
```

### 4. Run the Backend (FastAPI)

Install dependencies and launch the dev server:

```bash
uv pip install -r requirements.txt
uvicorn app.web_main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Run the Frontend (React + Vite)

In a separate terminal, install packages and launch the client dev server:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### 6. Run Unit & Integration Tests

Verify agent code, RAG, and Web API routes:

```bash
python -m pytest
```

---

## ⚠️ Known Limitations

1. **Row Limits:** Database result previews are capped at 50 rows to protect memory limits.
2. **Anonymous Sessions:** Anonymous session cookie validation isolates datasets. Clearing browser cookies will reset the active session index.
3. **Flat Files Only:** Custom datasets are limited to single-table flat files (one CSV or Excel sheet). Relational multi-table custom uploads are not supported in this version.
