# Harborstone Insurance — MCP AI Agent with State Graphs

An AI-powered assistant for marine insurance operations, built on the **Model Context Protocol (MCP)** with **stateful graph-based workflows** for complex multi-step processes.

Employees can check claims, retrieve policy information, file new claims, approve high-value decisions, perform AI-assisted risk assessments, manage long conversations, and now execute **stateful, recoverable workflows** with **Human-in-the-Loop** approval and **ticket-based failure recovery**.

This project demonstrates a complete MCP client/server implementation consisting of:

- A Python **MCP server** built with FastMCP exposing tools, resources, and prompts backed by a SQL Server database.
- A Python **MCP agent** that connects to the server, uses **Groq Llama 3** for reasoning and tool calling, and provides an interactive terminal interface.
- A **Memory & RAG module** that provides long-term memory and grounded document retrieval.
- A **Context Evaluation framework** that compares multiple long-context management strategies using realistic insurance conversations.
- **State Graph Agents** with checkpointing, Human-in-the-Loop (HITL), and ticket-based failure recovery.
- A **Web Platform** where users can chat with agents and admins can manage tools, documents, HITL tasks, and tickets.

---

## Features

- **Conversational access to company data** — ask natural-language questions about claims, policies, customers, and underwriting information.
- **Role-based permissions** — Claims Officer, Underwriter, Risk Analyst, and Admin roles each have different permissions.
- **Human-in-the-loop approval** — claims above $10,000 require explicit human confirmation before approval.
- **AI-assisted risk assessment** — combines deterministic underwriting rules with LLM-generated explanations.
- **Audit logging** — important actions are stored inside the AuditLogs table.
- **Reusable MCP resources and prompts** — underwriting guidelines, compliance policy, and denial letter templates.
- **Memory & Retrieval-Augmented Generation (RAG)** — enables the assistant to remember previous information and retrieve company knowledge from documents.
- **Long-context management evaluation** — implements and evaluates multiple context pruning strategies for handling conversations that exceed the model context window.
- **Automated benchmarking** — compares context strategies using Accuracy, Remaining Tokens, and Latency.
- **State Graph Agents** — stateful, recoverable workflows for complex multi-step processes.
- **Human-in-the-Loop (HITL)** — pause execution for human approval with platform-based resolution.
- **Ticket-based Failure Recovery** — unplanned failures create inspectable tickets for admin investigation.
- **Checkpointing** — crash recovery with durable state persistence after every transition.
- **Web Platform** — user chat interface and admin dashboard for tool/document management.

---

## Architecture
User
│
▼
Web Platform (platform/app.py)
│
├── User Chat Interface
│ └── Agent Switching (Appeal, Renewal, Fraud, Memory_RAG, Planning)
│
└── Admin Dashboard
├── Tool Management (enable/disable per agent)
├── RAG Document Management
├── HITL Task Resolution
└── Ticket Resolution
│
▼
State Graph Agents (state_graph/)
│
├── Appeal Graph (ToT + Constrained ReAct)
├── Renewal Graph (RAG + Task Decomposition)
└── Fraud Graph (LATS + Constrained ReAct)
│
├── Checkpointing (PlatformGraphCheckpoints)
├── HITL Tasks (PlatformHITLTasks)
└── Tickets (PlatformTickets)
│
▼
MCP Agent (agent.py)

Groq Llama 3 reasoning & tool calling

Memory integration

RAG retrieval

Context management
│
│ MCP Protocol over stdio
▼
MCP Server (server.py)

FastMCP tools

Resources

Prompts

Human approval

Role-based permissions
│
▼
SQL Server Database
│
├──────────────────────┬──────────────────────┬──────────────────────┐
▼ ▼ ▼
Memory Module RAG Module Platform Tables

Short-Term Memory - Chroma Vector DB - PlatformHITLTasks

Semantic Memory - HNSW Index - PlatformTickets

Episodic Memory - Metadata Store - PlatformGraphCheckpoints

Consolidation Layer - Embedding Pipeline - PlatformToolRegistry

Promote/Drop Logic - Retrieval Methods - PlatformRAGDocuments
│
├──────────────────────┴──────────────────────┐
▼ ▼
Context Evaluation Retrieval Evaluation

Sliding Window - Naive RAG

Observation Masking - Hybrid RAG (Vector + BM25)

Recursive Summarization - Agentic RAG (Multi-hop)

Zone-Based Pruning - Self-RAG Verification

text

---

## Tech Stack

- Python 3.11+
- FastMCP
- MCP Python SDK
- Groq API (Llama 3)
- SQL Server
- pyodbc
- ChromaDB (Vector Database)
- Sentence-Transformers (all-MiniLM-L6-v2)
- rank_bm25 (Keyword Search)
- Pydantic
- python-dotenv
- Pytest
- FastAPI (Web Platform)
- LangChain Core

---

## Prerequisites

- Python 3.11 or later
- SQL Server (local or remote)
- ODBC Driver 18 for SQL Server
- A Groq API Key
- Git

---

## Project Structure
Harborstone-Insurance-Company/
├── agent/
│ └── agent.py # MCP Agent with RAG integration
├── mcp_server/
│ └── server.py # FastMCP Server
├── platform/ # Web Platform
│ ├── app.py # FastAPI application
│ ├── database.py # Platform database operations
│ ├── models.py # Pydantic models
│ ├── hitl.py # HITL task management
│ ├── tickets.py # Ticket management
│ ├── static/ # Static files (CSS, JS)
│ └── templates/ # HTML templates
├── state_graph/ # State Graph Agents
│ ├── init.py
│ ├── base_graph.py # Base class with checkpointing
│ ├── llm_additions.py # LLM techniques (ToT, LATS, etc.)
│ ├── appeal_graph.py # Appeal Graph (ToT + Constrained ReAct)
│ ├── renewal_graph.py # Renewal Graph (RAG + Decomposition)
│ └── fraud_graph.py # Fraud Graph (LATS + Constrained ReAct)
├── planning_lab/ # Planning algorithms
│ ├── algorithms/
│ │ ├── decomposition.py
│ │ ├── tree_of_thoughts.py
│ │ ├── lats.py
│ │ └── self_refine.py
│ └── models.py
├── memory/ # Memory system
├── RAG/ # Retrieval-Augmented Generation
├── context_eval/ # Context evaluation
├── retrieval_eval/ # Retrieval evaluation
├── chroma_db/ # Vector database
├── data/ # Data files
├── db/ # Database scripts
├── tests/
│ ├── test_state_graphs.py # State graph tests
│ ├── test_integration.py # Integration tests
│ └── test_mcp.py # MCP tests
├── .env # Environment variables
├── requirements.txt
└── README.md

text

---

## State Graph Agents

### Overview

The system includes three **stateful, recoverable graph agents** for complex business processes that span multiple turns, wait for external events, or require human approval.

Each graph implements:
- **Checkpointing** — state persisted after every transition for crash recovery
- **HITL (Human-in-the-Loop)** — pauses for human approval via the platform
- **Tickets** — unplanned failures create inspectable tickets
- **Two LLM additions** per graph from: Tree of Thoughts, LATS, Constrained ReAct, Task Decomposition, or RAG

### The Three State Graphs

| Graph | Problem | Why Stateful | LLM Additions |
|-------|---------|--------------|---------------|
| **Appeal Graph** | Multi-day claim appeal process | Waits for customer documents, underwriter review, manager escalation | Tree of Thoughts (strategy selection) + Constrained ReAct (form submission) |
| **Renewal Graph** | Policy renewal with external data | Waits for vessel inspection report (24-72 hours), risk assessment, underwriter review | RAG (underwriting guidelines) + Task Decomposition (sub-tasks) |
| **Fraud Graph** | Cross-department fraud investigation | Claims → Underwriting → Legal review chain, branching decisions | LATS (investigation ordering) + Constrained ReAct (whitelisted actions) |

### State Flow Diagrams

**Appeal Graph:**
start → claim_denied → appeal_started → appeal_strategy (ToT) → awaiting_documents (HITL)
→ documents_received → submitting_appeal (Constrained ReAct) → underwriter_review (HITL)
→ appeal_approved OR appeal_denied → (escalated_to_manager HITL) → end

text

**Renewal Graph:**
start → renewal_started → fetch_vessel_details → decompose_renewal (Decomposition)
→ await_inspection_report (wait) → report_received OR report_timeout (ticket)
→ risk_assessment (RAG + ToT) → auto_renew OR underwriter_review (HITL) → end

text

**Fraud Graph:**
start → fraud_flagged → claims_review (HITL) → fraud_cleared OR underwriting_review (HITL)
→ fraud_cleared OR legal_review (HITL) → fraud_cleared OR fraud_confirmed → end

text

### Checkpointing & Crash Recovery

Every node transition saves a checkpoint to the `PlatformGraphCheckpoints` table. If the process crashes, it resumes exactly from the last checkpoint.

**Test Proof:** `test_appeal_graph_crash_recovery` passes, demonstrating crash recovery.

### Human-in-the-Loop (HITL)

HITL nodes pause execution and create a task in the `PlatformHITLTasks` table. The admin resolves it through the platform UI.

### Tickets

Unplanned failures (timeouts, API errors, validation failures) create tickets in the `PlatformTickets` table.

---

## Web Platform

### User Interface

- **Agent Switching** — users can switch between agents (Appeal, Renewal, Fraud, Memory_RAG, Planning)
- **Chat Interface** — send messages and see agent responses
- **Session Persistence** — stateful conversations with session IDs

### Admin Dashboard

| Feature | Description |
|---------|-------------|
| **Tool Management** | Enable/disable MCP tools per agent |
| **RAG Document Management** | Add/remove/activate documents for retrieval |
| **HITL Tasks** | View and resolve pending human approvals |
| **Tickets** | View and resolve system failures |

### Platform Tables

The platform uses these SQL Server tables:

| Table | Purpose |
|-------|---------|
| `PlatformHITLTasks` | HITL tasks awaiting admin approval |
| `PlatformTickets` | System failures needing investigation |
| `PlatformGraphCheckpoints` | Durable checkpoints for crash recovery |
| `PlatformToolRegistry` | Tool permissions per agent |
| `PlatformRAGDocuments` | Admin-managed RAG documents |

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd Harborstone-Insurance-Company
2. Create a virtual environment
Windows

bash
python -m venv .venv
.venv\Scripts\activate
Linux / macOS

bash
source .venv/bin/activate
3. Install dependencies
bash
pip install -r requirements.txt
4. Configure the database
Create the SQL Server database:

text
HarborstoneInsurance
Run the SQL scripts inside the db/ folder:

text
create_database.sql
seed_data.sql
queries.sql
5. Configure environment variables
Create a .env file in the project root.

Example:

env
# SQL Server
WIN_DB_SERVER=localhost\SQLEXPRESS
WIN_DB_NAME=HarborstoneInsurance
WIN_DB_DRIVER=ODBC Driver 18 for SQL Server
WIN_DB_AUTH_TYPE=WINDOWS

# If SQL Authentication is used:
# WIN_DB_USERNAME=your_username
# WIN_DB_PASSWORD=your_password

# MCP
TRANSPORT_TYPE=stdio

# Groq
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
Running the Project
Start the Platform
bash
python platform/app.py
Then open: http://localhost:8000

Start the MCP Agent (Terminal)
The MCP Agent automatically launches the MCP Server.

bash
python agent/agent.py
The startup sequence is:

Launch MCP Server

Complete MCP handshake

Discover available tools

Load MCP resources

Load MCP prompts

Initialize RAG system (auto-indexes the policy manual)

User login

Interactive AI chat begins

Testing
Run All Tests
bash
pytest tests/ -v
Run State Graph Tests
bash
pytest tests/test_state_graphs.py -v
Run Integration Tests
bash
pytest tests/test_integration.py -v
Run MCP Tests
bash
pytest tests/test_mcp.py -v
Test Results
text
tests/test_state_graphs.py::TestStateGraphs::test_appeal_graph PASSED
tests/test_state_graphs.py::TestStateGraphs::test_renewal_graph PASSED
tests/test_state_graphs.py::TestStateGraphs::test_fraud_graph PASSED
tests/test_state_graphs.py::TestStateGraphs::test_appeal_graph_crash_recovery PASSED

==================== 4 passed in 27.58s ====================
Available MCP Tools
Tool	Description	Access
login	Authenticate and start a session	Everyone
check_claim_status	Retrieve claim information	Everyone
get_customer_info	Retrieve customer information	Everyone
get_policy_details	Retrieve policy information	Everyone
file_claim	Submit a new insurance claim	Everyone
approve_claim	Approve or reject claims (Human Approval for high-value claims)	Underwriter, Risk Analyst, Admin
assess_risk	AI-assisted insurance risk assessment	Everyone
Roles & Approval Limits
Role	Can Approve Claims?	Approval Limit
Claims Officer	No	—
Risk Analyst	Yes	Up to $50,000
Underwriter	Yes	Up to $100,000
Admin	Yes	Unlimited
Claims exceeding $10,000 always require explicit human confirmation before approval.

MCP Resources & Prompts
Resources

underwriting://guidelines

compliance://policy

Prompts

draft_denial_letter

RAG (Retrieval-Augmented Generation)
The agent uses RAG to answer knowledge-based questions by grounding responses in the Harborstone Insurance Policy Manual.

How RAG Works in the Agent
User asks a knowledge question (contains words like "policy," "section," "guideline," etc.)

Agent detects it's a knowledge question using pattern matching

RAG retrieves relevant chunks from the vector database

Self-RAG verification checks if the answer is supported and relevant

If verified, the agent returns the grounded answer with source citation

If not verified, the agent falls back to tool-based approach

Implemented Retrieval Architectures
Architecture	Description
Naive RAG	Chunk → embed → retrieve top-5 → generate answer with retrieved chunks. Fastest and most cost-effective.
Hybrid RAG	Combines vector similarity with BM25 keyword search using Reciprocal Rank Fusion (RRF).
Agentic RAG	Multi-step reasoning loop: retrieves, grades relevance, rewrites query if needed, retrieves again.
Self-RAG Verification
Before returning an answer, the agent performs two checks:

Faithfulness: Does the answer strictly follow from the retrieved context?

Relevance: Does the answer directly address the question?

If both pass, the answer is returned with a source citation.

Retrieval Evaluation Results
Architecture	Accuracy (out of 12)	Avg Tokens/Query	Avg Latency
Naive RAG	10/12 (83%)	277	0.41s
Hybrid RAG	10/12 (83%)	320	1.24s
Agentic RAG	9/12 (75%)	328	16.03s
Why Naive RAG Was Chosen
Despite Hybrid Search being theoretically superior, our comparison table shows it offers zero accuracy gain over Naive RAG (both score 10/12) while incurring 3x the latency (1.24s vs 0.41s). Agentic RAG was disqualified due to its prohibitive 16-second latency—making it unsuitable for live underwriting calls where agents expect sub-second responses.

We chose Naive RAG because it delivers the highest accuracy at the lowest cost and latency, directly aligning with our business requirement for fast, accurate policy lookups during live calls.

RAG Configuration
The RAG system is configured in RAG/config.py:

python
DEFAULT_RETRIEVER = "naive"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
DEFAULT_TOP_K = 5
RETRIEVAL_CANDIDATE_K = 10
FUSION_FINAL_K = 5
Memory System
The agent includes a layered memory system designed to preserve useful conversation information while keeping the active context manageable.

Memory Architecture
Component	Purpose
Short-Term Memory	Keeps the active conversation messages and recent context.
Scratchpad	Stores temporary working information used during the current reasoning process.
Episodic Memory	Stores important conversation events and large messages that may be useful later.
Semantic Memory	Stores durable facts extracted from conversation summaries.
Consolidation Layer	Routes short-term messages to the appropriate long-term memory layer.
Promotion Strategy	Decides whether a message should be kept, promoted to episodic memory, promoted to semantic memory, or dropped.
Memory Flow
text
User / Agent Message
        │
        ▼
Short-Term Memory
        │
        ▼
Promotion Strategy
        │
        ├── KEEP ───────────────► Short-Term Memory
        ├── EPISODIC ───────────► Episodic Memory
        ├── SEMANTIC ────────────► Semantic Memory
        └── DROP ────────────────► Discarded
Context Management Evaluation
Large Language Models have a limited context window. As conversations become longer, important information may be forgotten or the prompt may exceed the model's token limit.

To address this challenge, a dedicated Context Evaluation Framework was implemented to compare multiple context pruning strategies on realistic long-running insurance conversations.

Implemented Strategies
Strategy	Description
Sliding Window	Keeps only the most recent conversation messages. Very fast but loses historical information.
Observation Masking	Masks old tool outputs while preserving the user-assistant conversation. Preserves important information.
Recursive Summarization	Summarizes older conversation history using an LLM while preserving key information. Best token reduction.
Zone-Based Pruning	Divides conversation into zones: keep newest, mask recent tool outputs, summarize older history, remove oldest.
Evaluation Results
Strategy	Accuracy	Remaining Tokens	Latency (s)
Sliding Window	0.00%	68	0.000001
Observation Masking	100.00%	283	0.000120
Recursive Summarization	100.00%	131	0.456764
Zone-Based Pruning	0.00%	227	0.300230
Selected Strategy
Recursive Summarization was selected as the preferred long-context management strategy. Although it introduces additional latency, it successfully preserved all critical information while reducing the average context size by more than 50%.

Contributors
Person B — State Graph Implementation
Contributions:

Designed and implemented the BaseStateGraph class with:

Durable checkpointing (PlatformGraphCheckpoints)

HITL task creation (PlatformHITLTasks)

Ticket creation (PlatformTickets)

Node execution with timeout handling

Crash recovery and resume functionality

Implemented llm_additions.py with wrappers for:

Tree of Thoughts (from planning_lab/)

LATS (from planning_lab/)

Task Decomposition (from planning_lab/)

Constrained ReAct (Self-Refine from planning_lab/)

RAG retrieval (from RAG/)

Built three state graphs:

Appeal Graph — multi-day claim appeal with ToT + Constrained ReAct

Renewal Graph — policy renewal with RAG + Task Decomposition

Fraud Graph — fraud investigation with LATS + Constrained ReAct

Integrated graphs into the platform (app.py)

Created test suite with 4 passing tests

Updated platform/hitl.py and platform/tickets.py for reliable ID retrieval

Other Contributors
MCP Server implementation

AI Agent implementation

Memory System

Retrieval-Augmented Generation (RAG)

Context Evaluation Framework

SQL Database Design

Platform UI/Admin Dashboard

Known Limitations
Login currently verifies only the username. Password authentication is not yet implemented.

The MCP server currently uses stdio transport, supporting a single local client.

Recursive Summarization depends on an external LLM, which increases response latency.

Context evaluation currently uses a fixed collection of test conversations rather than dynamically generated workloads.

The selected context management strategy is configured manually and is not automatically chosen based on conversation length.

The RAG corpus is currently limited to a single policy manual.

Agentic RAG shows poor performance due to query rewriting and grading limitations.

Future Improvements
MCP

Support HTTP and WebSocket transport.

Multi-user concurrent sessions.

Stronger authentication with password hashing and JWT.

More insurance-related MCP tools.

State Graphs

Add more graphs for additional business processes.

Support for parallel node execution.

Better visual graph representation.

Dynamic graph modification at runtime.

Platform

User authentication and sessions.

Real-time notifications for HITL tasks.

Better UI/UX with streaming responses.

Memory

Persistent long-term memory stored in a database.

Automatic memory consolidation.

Better episodic memory retrieval.

Adaptive scratchpad management.

Retrieval-Augmented Generation (RAG)

Re-ranking retrieved documents before generation.

Incremental indexing for newly added documents.

Support for multiple document collections.

Better query rewriting for Agentic RAG.

Caching of retrieval results to reduce latency.

Context Management

Hybrid strategy combining Observation Masking and Recursive Summarization.

Dynamic strategy selection based on the current context size.

Automatic pruning when the token limit is reached.

Better summarization prompts specialized for insurance conversations.

AI Agent

Integrate the Context Evaluation framework directly into the live MCP Agent.

Allow the agent to automatically switch between pruning strategies.

Support continuous long conversations without exceeding the model context window.

License
This project was developed for educational purposes as part of a university training program.

It is intended to demonstrate:

Model Context Protocol (MCP)

Long-Term Memory

Retrieval-Augmented Generation (RAG)

Context Management Strategies

AI Agent Design

Human-in-the-loop workflows

State Graph Architectures

Crash Recovery & Checkpointing

No commercial use is intended.