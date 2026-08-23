# Harborstone Insurance — MCP AI Agent with State Graphs

An AI-powered assistant for marine insurance operations, built on the **Model Context Protocol (MCP)** with **stateful graph-based workflows** for complex multi-step processes.

Employees can check claims, retrieve policy information, file new claims, approve high-value decisions, perform AI-assisted risk assessments, manage long conversations, and execute **stateful, recoverable workflows** with **Human-in-the-Loop (HITL)** approval and **ticket-based failure recovery**.

The project consists of:

- A Python **MCP server** (`mcp_server/`) built with FastMCP, exposing tools, resources, and prompts backed by a SQL Server database.
- A Python **MCP agent** (`agent/`) that connects to the server over stdio, uses **Groq** for reasoning and tool calling, and provides an interactive terminal chat.
- A **Memory & RAG module** (`memory/`, `RAG/`) providing long-term memory and grounded document retrieval.
- A **Context Evaluation framework** (`context_eval/`) comparing long-context management strategies on realistic insurance conversations.
- **State Graph Agents** (`state_graph/`) with checkpointing, HITL, and ticket-based failure recovery for Appeal, Renewal, and Fraud workflows.
- A **Web Platform** (`web_platform/`) — a FastAPI app where users chat with the three state-graph agents and admins manage tools, RAG documents, HITL tasks, and tickets.
- A **Planning Lab** (`planning_lab/`, `planning_agent/`, `planning_eval/`) implementing task-decomposition and reasoning strategies (ToT, LATS, Reflexion, Self-Refine, Plan-and-Solve) used by the state graphs, plus a standalone `planning/` reference submodule.

---

## Features

- **Conversational access to company data** — natural-language questions about claims, policies, customers, and underwriting information.
- **Role-based permissions** — Claims Officer, Underwriter, Risk Analyst, and Admin roles each have different permissions.
- **Human-in-the-loop approval** — claims above $10,000 require explicit human confirmation before approval.
- **AI-assisted risk assessment** — combines deterministic underwriting rules with LLM-generated explanations.
- **Audit logging** — key actions are recorded in the `AuditLogs` table.
- **Reusable MCP resources and prompts** — underwriting guidelines, compliance policy, and a denial-letter template.
- **Memory & Retrieval-Augmented Generation (RAG)** — lets the terminal agent remember prior context and ground answers in company documents.
- **Long-context management evaluation** — implements and benchmarks multiple context-pruning strategies.
- **State Graph Agents** — stateful, recoverable workflows for Appeal, Renewal, and Fraud processes, each combining two reasoning techniques from the Planning Lab.
- **Checkpointing & crash recovery** — durable state persisted to SQL Server after every node transition.
- **Ticket-based failure recovery** — unplanned failures create inspectable tickets for admin review.
- **Web Platform** — chat UI for the state-graph agents plus an admin dashboard for tools, documents, HITL tasks, and tickets.

---

## Architecture

```
User
  │
  ▼
Web Platform (web_platform/app.py)
  │
  ├── Chat UI ── agent = appeal | renewal | fraud
  │
  └── Admin Dashboard
        ├── Tool Registry (enable/disable MCP tools per agent)
        ├── RAG Document Management
        ├── HITL Task Resolution
        └── Ticket Resolution
  │
  ▼
State Graph Agents (state_graph/)
  ├── Appeal Graph   — Tree of Thoughts + Constrained ReAct (Self-Refine)
  ├── Renewal Graph  — RAG + Task Decomposition
  └── Fraud Graph    — LATS + Constrained ReAct (Self-Refine)
        │
        ├── Checkpointing → PlatformGraphCheckpoints
        ├── HITL Tasks    → PlatformHITLTasks
        └── Tickets       → PlatformTickets
  │
  ▼ (state graphs call MCP tools directly via mcp_server.server.call_tool)
MCP Server (mcp_server/server.py)
  ├── FastMCP tools, resources, prompts
  ├── Role-based permissions & human approval (elicitation)
  └── Reads/writes SQL Server directly via pyodbc

─────────────────────────────────────────────

Terminal MCP Agent (agent/agent.py)  — separate entry point, connects to the
same MCP server over stdio as its own client process
  ├── Groq reasoning & tool calling
  ├── RAG retrieval (RAG/)
  └── Short-Term / Episodic / Semantic memory (memory/)

─────────────────────────────────────────────

SQL Server Database
  ├── Business tables: Customers, Employees, Vessels, InsurancePolicies,
  │   CoverageTypes, PolicyCoverage, Claims, FraudChecks, AuditLogs,
  │   ClaimWorkflow, Payments
  └── Platform tables: PlatformHITLTasks, PlatformTickets,
      PlatformGraphCheckpoints, PlatformToolRegistry, PlatformRAGDocuments

─────────────────────────────────────────────

Supporting evaluation frameworks (offline, not wired into the live app):
  ├── context_eval/    — Sliding Window, Observation Masking,
  │                      Recursive Summarization, Zone-Based Pruning
  ├── retrieval_eval/  — Naive RAG, Hybrid RAG, Agentic RAG
  └── planning_eval/   — compares decomposition vs. self-refine strategies
```

> **Note on agents:** the Web Platform currently exposes exactly **three** chat agents — `appeal`, `renewal`, `fraud` (see `web_platform/app.py`, `/api/agents`). The RAG/Memory system and the Planning Lab are used by the **terminal agent** (`agent/agent.py`) and by the state graphs internally, but they are not separately selectable agents in the web UI.

---

## Tech Stack

- Python 3.11+
- FastMCP (server) / MCP Python SDK (`mcp`, client — used by `agent/agent.py` and the planning lab's own MCP client)
- Groq API (chat completions)
- FastAPI + Jinja2 + Uvicorn (web platform)
- SQL Server + `pyodbc`
- ChromaDB (vector store) + `sentence-transformers` (`all-MiniLM-L6-v2`)
- `rank_bm25` (keyword search for Hybrid RAG)
- LangChain Core + `langchain-groq` (planning agent/orchestrator LLM wrappers)
- NetworkX (DAG validation/topological sort in `planning_lab`)
- Pydantic, python-dotenv, Pytest

---

## Prerequisites

- Python 3.11 or later
- SQL Server (local or remote) with an ODBC driver installed (e.g. **ODBC Driver 18 for SQL Server**)
- A Groq API key
- Git

---

## Project Structure

```
project/
├── agent/
│   └── agent.py              # Terminal MCP agent (Groq + RAG + memory)
├── mcp_server/
│   └── server.py              # FastMCP server (tools/resources/prompts, DB access)
├── web_platform/               # Web Platform (FastAPI)
│   ├── app.py                  # FastAPI app & routes
│   ├── database.py             # All SQL Server access for the platform
│   ├── models.py                # Pydantic request/response models
│   ├── hitl.py                  # HITL task helpers
│   ├── tickets.py               # Ticket helpers
│   ├── static/                  # CSS/JS
│   └── templates/               # Jinja2 HTML templates
├── state_graph/                 # State Graph Agents
│   ├── __init__.py
│   ├── base_graph.py            # Base class: checkpointing, HITL, tickets, timeouts
│   ├── llm_additions.py         # Wrappers around planning_lab algorithms + RAG
│   ├── appeal_graph.py          # ToT + Constrained ReAct
│   ├── renewal_graph.py         # RAG + Task Decomposition
│   └── fraud_graph.py           # LATS + Constrained ReAct
├── planning_lab/                 # Reasoning algorithm implementations
│   ├── algorithms/               # decomposition, ToT, LATS, self-refine, reflexion, plan-and-solve
│   ├── cli.py
│   └── models.py
├── planning_agent/               # Orchestrator that drives planning_lab via MCP + Groq
├── planning_eval/                 # Benchmarks planning strategies
├── planning/                       # Git submodule: original Mistral-based reference lab
├── memory/                          # Short-term / episodic / semantic memory + consolidation
├── RAG/                              # Retrieval (naive / hybrid / agentic / self-RAG)
├── context_eval/                      # Long-context pruning strategy benchmarks
├── retrieval_eval/                     # RAG architecture benchmarks
├── db/                                  # SQL scripts (schema, seed data, queries) + ERD.pdf
├── artifacts/                            # Saved evaluation run outputs (JSON)
├── chroma_db/                             # Local vector store (generated — see note below)
├── harborstone_manual.txt                  # Source document indexed by RAG
├── shared_interfaces.py                     # Unused — see Known Issues
├── tests/                                    # pytest suites (API, DB, integration, MCP, state graphs)
├── .env.example
├── requirements.txt
└── README.md
```

---

## State Graph Agents

### Overview

The system includes three **stateful, recoverable graph agents** for business processes that span multiple turns, wait for external events, or require human approval.

Each graph implements:
- **Checkpointing** — state persisted after every transition, for crash recovery.
- **HITL (Human-in-the-Loop)** — pauses for human approval via the platform.
- **Tickets** — unplanned failures create inspectable tickets.
- **Two reasoning techniques**, taken from the Planning Lab (Tree of Thoughts, LATS, Task Decomposition, RAG, Self-Refine/Constrained ReAct).

### The Three State Graphs

| Graph | Problem | Why Stateful | Reasoning Techniques |
|---|---|---|---|
| **Appeal Graph** | Multi-day claim appeal process | Waits for customer documents, underwriter review, manager escalation | Tree of Thoughts (strategy selection) + Constrained ReAct (form submission) |
| **Renewal Graph** | Policy renewal with external data | Waits for vessel inspection report, risk assessment, underwriter review | RAG (underwriting guidelines) + Task Decomposition (sub-tasks) |
| **Fraud Graph** | Cross-department fraud investigation | Claims → Underwriting → Legal review chain, branching decisions | LATS (investigation ordering) + Constrained ReAct (whitelisted actions) |

### State Flow (high level)

**Appeal Graph:**
`start → claim_denied → appeal_started → appeal_strategy (ToT) → awaiting_documents (HITL) → documents_received → submitting_appeal (Constrained ReAct) → underwriter_review (HITL) → appeal_approved | appeal_denied → (escalated_to_manager HITL) → end`

**Renewal Graph:**
`start → renewal_started → fetch_vessel_details → decompose_renewal (Decomposition) → await_inspection_report → report_received | report_timeout (ticket) → risk_assessment (RAG) → auto_renew | underwriter_review (HITL) → end`

**Fraud Graph:**
`start → fraud_flagged → claims_review (HITL) → fraud_cleared | underwriting_review (HITL) → fraud_cleared | legal_review (HITL) → fraud_cleared | fraud_confirmed → end`

### Checkpointing & Crash Recovery

Every node transition saves a checkpoint to `PlatformGraphCheckpoints`. If the process crashes, it can resume from the last checkpoint.

### Human-in-the-Loop (HITL)

HITL nodes pause execution and create a task in `PlatformHITLTasks`, resolved by an admin through the platform UI (`/api/admin/hitl/{task_id}/resolve` or `/resume`).

### Tickets

Unplanned failures (timeouts, API errors, validation failures) create tickets in `PlatformTickets`, viewable and resolvable at `/api/admin/tickets`.

---

## Web Platform

### User Interface

- **Chat Interface** — send messages to one of the three state-graph agents (`appeal`, `renewal`, `fraud`) and see responses.
- **Session Persistence** — conversations are tracked by `session_id`.

### Admin Dashboard

| Feature | Description |
|---|---|
| **Tool Management** | Enable/disable MCP tools per agent (`PlatformToolRegistry`) |
| **RAG Document Management** | Add/remove/activate documents for retrieval |
| **HITL Tasks** | View and resolve pending human approvals |
| **Tickets** | View and resolve system failures |

### Platform Tables

| Table | Purpose |
|---|---|
| `PlatformHITLTasks` | HITL tasks awaiting admin approval |
| `PlatformTickets` | System failures needing investigation |
| `PlatformGraphCheckpoints` | Durable checkpoints for crash recovery |
| `PlatformToolRegistry` | Tool permissions per agent |
| `PlatformRAGDocuments` | Admin-managed RAG documents |

---

## Setup

### 1. Clone the repository

```bash
git clone --recurse-submodules <your-repository-url>
cd <repo-folder>
```

The `planning/` folder is a **git submodule**. If you already cloned without `--recurse-submodules`, run:

```bash
git submodule update --init --recursive
```

### 2. Create a virtual environment

**Windows**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> The checked-in `requirements.txt` is missing a few packages that the code actually imports. Until it's updated, also install:
> ```bash
> pip install mcp langchain-core langchain-groq networkx
> ```
> (`mcp` is the official MCP client SDK used by `agent/agent.py` and `planning_agent/`, separate from `fastmcp` which is only used server-side. `networkx` is required by `planning_lab/models.py`.) If you plan to run the `planning/` submodule directly, also `pip install -r planning/requirements.txt` in its own environment — it targets Mistral instead of Groq.

### 4. Configure the database

Create the SQL Server database, then run the scripts in `db/` **in order**:

```
db/create_database.sql
db/seed_data.sql
```

`db/queries.sql` contains example/reference queries and is not required to run the app. `db/ERD.pdf` has the full entity-relationship diagram.

### 5. Configure environment variables

Copy `.env.example` to `.env` in the project root and fill it in:

```env
# SQL Server connection
WIN_DB_SERVER=localhost\SQLEXPRESS
WIN_DB_NAME=HarborstoneInsurance
WIN_DB_DRIVER=ODBC Driver 18 for SQL Server

# Auth mode: WINDOWS (Trusted_Connection) or SQL
WIN_DB_AUTH_TYPE=WINDOWS

# Only needed when WIN_DB_AUTH_TYPE=SQL
# WIN_DB_USERNAME=your_username
# WIN_DB_PASSWORD=your_password

# MCP transport (stdio is the only supported mode today)
TRANSPORT_TYPE=stdio

# Groq
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
```

> **Note:** the code reads `WIN_DB_AUTH_TYPE` to decide between Windows and SQL authentication — it does **not** read `WIN_TRUSTED_CONNECTION`, even though that name appears in `.env.example`. Set `WIN_DB_AUTH_TYPE=WINDOWS` (or `SQL`) explicitly. See Known Issues below.

---

## Running the Project

### Start the Web Platform

Run from the **project root** (both the templates and static-files paths are relative to the working directory):

```bash
python web_platform/app.py
```

Then open `http://localhost:8000`.

### Start the terminal MCP Agent

```bash
python agent/agent.py
```

This automatically launches the MCP server as a subprocess over stdio and walks through: server launch → MCP handshake → tool/resource/prompt discovery → RAG indexing of `harborstone_manual.txt` → login → interactive chat.

> See **Known Issues** — running this file directly currently executes the whole agent flow twice due to a duplicated entry point.

---

## Testing

```bash
pytest tests/ -v                     # everything
pytest tests/test_state_graphs.py -v # state graphs only
pytest tests/test_integration.py -v  # integration
pytest tests/test_mcp.py -v          # MCP server/tools
pytest tests/test_database.py -v     # database layer
pytest tests/test_api.py -v          # web platform API
```

Additional test suites live alongside their modules:

```bash
pytest memory/tests/ -v
pytest context_eval/tests/ -v
pytest planning_agent/test_decomposition.py -v
pytest planning/tests/ -v            # submodule, uses Mistral
```

All of the suites above talk to a real SQL Server database and, for the agent/LLM paths, real Groq (or Mistral, for `planning/`) API calls — they are not mocked. A configured `.env` and reachable database are required before running them.

---

## Available MCP Tools

| Tool | Description | Access |
|---|---|---|
| `login` | Authenticate and start a session | Everyone |
| `check_claim_status` | Retrieve claim information | Everyone |
| `get_customer_info` | Retrieve customer information | Everyone |
| `get_policy_details` | Retrieve policy information | Everyone |
| `file_claim` | Submit a new insurance claim | Everyone |
| `approve_claim` | Approve or reject claims (human confirmation for high-value claims) | Underwriter, Risk Analyst, Admin |
| `assess_risk` | AI-assisted insurance risk assessment | Everyone |

### Roles & Approval Limits

| Role | Can Approve Claims? | Approval Limit |
|---|---|---|
| Claims Officer | No | — |
| Risk Analyst | Yes | Up to $50,000 |
| Underwriter | Yes | Up to $100,000 |
| Admin | Yes | Unlimited |

Claims exceeding $10,000 always require explicit human confirmation before approval, regardless of role.

### MCP Resources & Prompts

**Resources:** `underwriting://guidelines`, `compliance://policy`
**Prompts:** `draft_denial_letter`

---

## RAG (Retrieval-Augmented Generation)

The terminal agent uses RAG to ground answers to knowledge questions in the Harborstone Insurance Policy Manual (`harborstone_manual.txt`), and the Renewal Graph uses it to retrieve underwriting guidelines.

### How RAG works in the terminal agent

1. The user asks a knowledge question (detected via pattern matching on words like "policy," "section," "guideline").
2. The RAG retriever pulls relevant chunks from the Chroma vector store.
3. A Self-RAG verifier checks the answer is faithful to the retrieved context and relevant to the question.
4. If verified, the agent returns the grounded answer with a source citation; otherwise it falls back to a tool-based approach.

### Implemented retrieval architectures

| Architecture | Description |
|---|---|
| Naive RAG | Chunk → embed → retrieve top-5 → generate. Fastest and most cost-effective. |
| Hybrid RAG | Vector similarity + BM25 keyword search, combined with Reciprocal Rank Fusion. |
| Agentic RAG | Multi-step loop: retrieve, grade relevance, rewrite query if needed, retrieve again. |

### Retrieval evaluation results (`retrieval_eval/`)

| Architecture | Accuracy (of 12) | Avg Tokens/Query | Avg Latency |
|---|---|---|---|
| Naive RAG | 10/12 (83%) | 277 | 0.41s |
| Hybrid RAG | 10/12 (83%) | 320 | 1.24s |
| Agentic RAG | 9/12 (75%) | 328 | 16.03s |

**Naive RAG** is used by default: it matches Hybrid RAG's accuracy at roughly a third of the latency, and comfortably beats Agentic RAG on both accuracy and latency.

### RAG configuration (`RAG/config.py`)

```python
DEFAULT_RETRIEVER = "naive"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
DEFAULT_TOP_K = 5
RETRIEVAL_CANDIDATE_K = 10
FUSION_FINAL_K = 5
```

---

## Memory System

The terminal agent includes a layered memory system that preserves useful conversation information while keeping the active context manageable.

| Component | Purpose |
|---|---|
| Short-Term Memory | Active conversation messages and recent context. |
| Scratchpad | Temporary working information during the current reasoning process. |
| Episodic Memory | Important conversation events and large messages that may be useful later. |
| Semantic Memory | Durable facts extracted from conversation summaries. |
| Consolidation Layer | Routes short-term messages to the appropriate long-term layer. |
| Promotion Strategy | Decides KEEP / EPISODIC / SEMANTIC / DROP for each message. |

```
User / Agent Message
        │
        ▼
Short-Term Memory
        │
        ▼
Promotion Strategy
        │
        ├── KEEP ─────► Short-Term Memory
        ├── EPISODIC ─► Episodic Memory
        ├── SEMANTIC ─► Semantic Memory
        └── DROP ─────► Discarded
```

Memory is currently in-process only (see Known Limitations).

---

## Context Management Evaluation

Since LLMs have a limited context window, `context_eval/` implements and compares strategies for keeping long insurance conversations within budget.

| Strategy | Description |
|---|---|
| Sliding Window | Keeps only the most recent messages. Very fast, loses history. |
| Observation Masking | Masks old tool outputs while preserving the user-assistant conversation. |
| Recursive Summarization | LLM-summarizes older history while preserving key information. Best token reduction. |
| Zone-Based Pruning | Newest kept, recent tool outputs masked, older history summarized, oldest removed. |

### Evaluation results

| Strategy | Accuracy | Remaining Tokens | Latency (s) |
|---|---|---|---|
| Sliding Window | 0.00% | 68 | 0.000001 |
| Observation Masking | 100.00% | 283 | 0.000120 |
| Recursive Summarization | 100.00% | 131 | 0.456764 |
| Zone-Based Pruning | 0.00% | 227 | 0.300230 |

**Recursive Summarization** is the selected strategy: it preserves all critical information while cutting average context size by more than half, at an acceptable latency cost. This evaluation framework is not yet wired into the live terminal agent — see Known Limitations.

---

## Known Issues

These were found while reviewing the project and should be addressed before relying on it in production:

1. **`agent/agent.py` runs its whole flow twice.** The file ends with two separate `if __name__ == "__main__": asyncio.run(main())` blocks. Running `python agent/agent.py` executes `main()` to completion once, then immediately executes it a second time. This is almost certainly a merge/copy-paste leftover — remove the second block.

2. **`requirements.txt` is missing real dependencies.** The code imports `mcp` (client SDK), `langchain_core`, `langchain_groq`, and `networkx`, none of which are listed in the root `requirements.txt` (only `fastmcp` and `langchain-text-splitters` are). A fresh `pip install -r requirements.txt` will not be enough to run `agent/agent.py`, `planning_agent/`, `planning_eval/`, or `planning_lab/models.py`.

3. **`.env.example` doesn't match what the code reads.** `WIN_TRUSTED_CONNECTION=yes` is not read anywhere — `mcp_server/server.py` reads `WIN_DB_AUTH_TYPE` instead, which isn't in `.env.example`. Neither are `WIN_DB_USERNAME`/`WIN_DB_PASSWORD`, needed for the SQL-auth branch. As shipped, `.env.example` gives no working way to select or configure authentication mode explicitly (it happens to fall back to the `WINDOWS` default, but only by coincidence).

4. **The Web Platform only supports three agents, not five.** `web_platform/app.py`'s `/api/agents` and `/api/chat` only recognize `appeal`, `renewal`, and `fraud`. RAG/Memory and the Planning Lab exist as separate modules used elsewhere (the terminal agent, the state graphs), but they are not selectable chat agents in the web UI. Documentation or UI copy claiming otherwise should be corrected.

5. **`shared_interfaces.py` is dead code.** It's never imported anywhere in the project. It re-implements `create_hitl_task`, `create_ticket`, and `save_checkpoint`/`load_checkpoint` against `web_platform.database`/`web_platform.hitl`/`web_platform.tickets` independently of `state_graph/base_graph.py`, which talks to `web_platform.database` directly. Since nothing calls it, it can only drift out of sync with the real implementation — either wire it up or delete it.

6. **The web app must be started from the project root.** `web_platform/app.py` mounts static files and templates using the relative paths `"web_platform/static"` and `"web_platform/templates"`. Running it from inside the `web_platform/` directory (e.g. `cd web_platform && python app.py`) will fail to find them.

7. **A handful of bare `except:` clauses** (`state_graph/renewal_graph.py`, `state_graph/fraud_graph.py`, `web_platform/app.py`, `planning_agent/environment.py`) silently swallow all exceptions, including ones you'd normally want to see (and `KeyboardInterrupt`). Worth narrowing to specific exception types.

8. **A few f-strings are missing their placeholders** — e.g. `state_graph/fraud_graph.py:273`, `web_platform/app.py:271`, and several spots in `tests/test_integration.py` / `tests/test_database.py`. These look like debug print statements that lost their `{variable}` during editing; worth a quick pass to confirm no information is being silently dropped from log/error messages.

9. **`chroma_db/` isn't excluded by `.gitignore`.** It contains a generated, binary vector index. Left untracked, it will bloat the git history the first time someone commits after indexing; consider adding it to `.gitignore` and regenerating it on first run instead.

10. **Static analysis, not full runtime testing.** All 92 Python files compile cleanly (no syntax errors) and pass a `pyflakes` pass with only minor, non-blocking warnings (mostly unused imports/locals, listed in items 7–8 above). The test suite requires a live SQL Server instance and real Groq/Mistral API keys, so it was reviewed statically here rather than executed — treat the above as a code review, not a test run.

**Also worth flagging outside the code itself:** the uploaded archive includes a real `.env` file alongside the source. `.gitignore` correctly excludes `.env` from version control, so it likely isn't in git history — but since it left your machine in this zip, it's worth rotating the Groq API key it contains as a precaution.

---

## Contributors

**Person B — State Graph Implementation**

- Designed and implemented `BaseStateGraph` with durable checkpointing (`PlatformGraphCheckpoints`), HITL task creation (`PlatformHITLTasks`), ticket creation (`PlatformTickets`), timeout-aware node execution, and crash recovery/resume.
- Implemented `llm_additions.py`: wrappers for Tree of Thoughts, LATS, Task Decomposition, Constrained ReAct (Self-Refine), and RAG retrieval, all built on `planning_lab/` and `RAG/`.
- Built the three state graphs (Appeal, Renewal, Fraud) and integrated them into the platform (`app.py`).
- Wrote the state-graph test suite.

**Other contributors:** MCP Server implementation · AI Agent implementation · Memory System · Retrieval-Augmented Generation (RAG) · Context Evaluation Framework · SQL Database Design · Platform UI/Admin Dashboard.

---

## Known Limitations

- Login currently verifies only the username; password authentication is not yet implemented.
- The MCP server uses stdio transport, supporting a single local client at a time.
- Recursive Summarization depends on an external LLM call, adding latency.
- Context evaluation uses a fixed set of test conversations rather than dynamically generated workloads, and its strategies aren't yet wired into the live terminal agent.
- The RAG corpus is currently limited to a single policy manual.
- Agentic RAG underperforms due to query-rewriting and grading limitations.
- Memory is in-process only — nothing persists across agent restarts.

## Future Improvements

**MCP:** HTTP/WebSocket transport · multi-user concurrent sessions · password hashing + JWT auth · more insurance tools.

**State Graphs:** additional business-process graphs · parallel node execution · visual graph representation · dynamic graph modification at runtime.

**Platform:** user authentication/sessions · real-time HITL notifications · streaming responses.

**Memory:** persistent storage in the database · automatic consolidation · better episodic retrieval · adaptive scratchpad management.

**RAG:** re-ranking · incremental indexing · multiple document collections · better query rewriting for Agentic RAG · retrieval result caching.

**Context Management:** hybrid Observation-Masking + Recursive-Summarization strategy · dynamic strategy selection based on context size · automatic pruning at the token limit.

**Agent:** integrate the Context Evaluation framework into the live terminal agent · automatic strategy switching · support for continuous long conversations without exceeding the context window.

---

## License

This project was developed for educational purposes as part of a university training program, to demonstrate the Model Context Protocol (MCP), long-term memory, Retrieval-Augmented Generation, context-management strategies, AI agent design, human-in-the-loop workflows, state-graph architectures, and crash recovery/checkpointing.
