# Harborstone Insurance — MCP AI Agent

An AI-powered assistant for marine insurance operations, built on the **Model Context Protocol (MCP)**.

Employees can check claims, retrieve policy information, file new claims, approve high-value decisions, perform AI-assisted risk assessments, and manage long conversations through intelligent context management.

This project demonstrates a complete MCP client/server implementation consisting of:

- A Python **MCP server** built with FastMCP exposing tools, resources, and prompts backed by a SQL Server database.
- A Python **MCP agent** that connects to the server, uses **Groq Llama 3** for reasoning and tool calling, and provides an interactive terminal interface.
- A **Memory & RAG module** that provides long-term memory and grounded document retrieval.
- A **Context Evaluation framework** that compares multiple long-context management strategies using realistic insurance conversations.

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

---

## Architecture

```
User
  │
  ▼
MCP Agent (agent.py)
  - Groq Llama 3 reasoning & tool calling
  - Memory integration
  - RAG retrieval
  - Context management
  │
  │  MCP Protocol over stdio
  ▼
MCP Server (server.py)
  - FastMCP tools
  - Resources
  - Prompts
  - Human approval
  - Role-based permissions
  │
  ▼
SQL Server Database
  │
  ├──────────────────────┬──────────────────────┐
  ▼                      ▼
Memory Module          RAG Module
  - Short-Term Memory    - Chroma Vector Database
  - Semantic Memory      - HNSW Index (Cosine)
  - Episodic Memory      - Metadata Store
  - Consolidation Layer  - Embedding Pipeline (all-MiniLM-L6-v2)
  │                      │
  ├──────────────────────┴──────────────────────┐
  ▼                                              ▼
Context Evaluation                     Retrieval Evaluation
  - Sliding Window                       - Naive RAG
  - Observation Masking                  - Hybrid RAG (Vector + BM25)
  - Recursive Summarization              - Agentic RAG (Multi-hop)
  - Zone-Based Pruning                   - Self-RAG Verification
```

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

---

## Prerequisites

- Python 3.11 or later
- SQL Server (local or remote)
- ODBC Driver 18 for SQL Server
- A Groq API Key
- Git

---

## Project Structure

```
Harborstone-Insurance-Company/
├── agent/
│   └── agent.py                  # MCP Agent with RAG integration
├── mcp_server/
│   └── server.py                 # FastMCP Server
├── memory/
│   ├── short_term.py
│   ├── semantic_memory.py
│   ├── episodic_memory.py
│   ├── consolidation.py
│   ├── scratchpad.py
│   ├── token_counter.py
│   ├── schema.py
│   └── ...
├── RAG/
│   ├── __init__.py
│   ├── config.py
│   ├── chunking.py
│   ├── embedding.py
│   ├── vector_store.py
│   ├── retriever.py
│   └── self_rag.py
├── context_eval/
│   ├── base_strategy.py
│   ├── sliding_window.py
│   ├── observation_masking.py
│   ├── recursive_summarization.py
│   ├── conversation_summarizer.py
│   ├── zone_based_pruning.py
│   ├── evaluator.py
│   ├── metrics.py
│   ├── long_context_cases.py
│   ├── run_evaluation.py
│   └── tests/
├── retrieval_eval/
│   ├── test.py
│   └── evaluation.py
├── chroma_db/
├── data/
│   └── harborstone_manual.txt
├── db/
├── .env
├── requirements.txt
└── README.md
```

---

## Setup

### 1. Clone the repository

```bash
git clone <your-repository-url>
cd Harborstone-Insurance-Company
```

### 2. Create a virtual environment

**Windows**

```bash
python -m venv .venv
.venv\Scripts\activate
```

**Linux / macOS**

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the database

Create the SQL Server database:

```
HarborstoneInsurance
```

Run the SQL scripts inside the `db/` folder:

```
create_database.sql
seed_data.sql
queries.sql
```

### 5. Configure environment variables

Create a `.env` file in the project root.

Example:

```env
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
```

---

## Running the Project

The MCP Agent automatically launches the MCP Server.

Simply run:

```bash
python agent/agent.py
```

The startup sequence is:

1. Launch MCP Server
2. Complete MCP handshake
3. Discover available tools
4. Load MCP resources
5. Load MCP prompts
6. Initialize RAG system (auto-indexes the policy manual)
7. User login
8. Interactive AI chat begins

---

## RAG (Retrieval-Augmented Generation)

The agent uses RAG to answer knowledge-based questions by grounding responses in the Harborstone Insurance Policy Manual.

### How RAG Works in the Agent

1. User asks a knowledge question (contains words like "policy," "section," "guideline," etc.)
2. Agent detects it's a knowledge question using pattern matching
3. RAG retrieves relevant chunks from the vector database
4. Self-RAG verification checks if the answer is supported and relevant
5. If verified, the agent returns the grounded answer with source citation
6. If not verified, the agent falls back to tool-based approach

### Implemented Retrieval Architectures

| Architecture | Description |
|---|---|
| Naive RAG | Chunk → embed → retrieve top-5 → generate answer with retrieved chunks. Fastest and most cost-effective. |
| Hybrid RAG | Combines vector similarity with BM25 keyword search using Reciprocal Rank Fusion (RRF). |
| Agentic RAG | Multi-step reasoning loop: retrieves, grades relevance, rewrites query if needed, retrieves again. |

### Self-RAG Verification

Before returning an answer, the agent performs two checks:

- **Faithfulness**: Does the answer strictly follow from the retrieved context?
- **Relevance**: Does the answer directly address the question?

If both pass, the answer is returned with a source citation.

### Retrieval Evaluation Results

| Architecture | Accuracy (out of 12) | Avg Tokens/Query | Avg Latency |
|---|---|---|---|
| Naive RAG | 10/12 (83%) | 277 | 0.41s |
| Hybrid RAG | 10/12 (83%) | 320 | 1.24s |
| Agentic RAG | 9/12 (75%) | 328 | 16.03s |

### Why Naive RAG Was Chosen

Despite Hybrid Search being theoretically superior, our comparison table shows it offers zero accuracy gain over Naive RAG (both score 10/12) while incurring 3x the latency (1.24s vs 0.41s). Agentic RAG was disqualified due to its prohibitive 16-second latency—making it unsuitable for live underwriting calls where agents expect sub-second responses.

We chose Naive RAG because it delivers the highest accuracy at the lowest cost and latency, directly aligning with our business requirement for fast, accurate policy lookups during live calls.

### RAG Configuration

The RAG system is configured in `RAG/config.py`:

```python
# Which retriever to use by default
DEFAULT_RETRIEVER = "naive"

# Vector store settings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
DEFAULT_TOP_K = 5

# Hybrid search settings
RETRIEVAL_CANDIDATE_K = 10
FUSION_FINAL_K = 5
```

---

## Example Session

### Knowledge Questions (Handled by RAG)

```
You: What is the standard deductible for a 22-year-old vessel?

======================================================================
RAG KNOWLEDGE QUERY DETECTED
======================================================================
Query: What is the standard deductible for a 22-year-old vessel?
----------------------------------------------------------------------
Verification passed: True
   Supported: True, Relevant: True
======================================================================

Agent:
The standard deductible for a vessel that is 22 years old is $2,500.

*Source: manual*
```

### Database Questions (Handled by MCP Tools)

```
You: check claim 4

======================================================================
MCP TOOL CALL: check_claim_status
======================================================================
{
  "claim_id": 4
}

MCP RESULT:
CLAIM STATUS REPORT
...
```

### Other Examples

```
You: get policy 7
You: assess the risk of policy 9
You: file a claim for policy 12
You: approve claim 18
```

Type `help` at any time to display all supported commands.

---

## Available MCP Tools

| Tool | Description | Access |
|---|---|---|
| `login` | Authenticate and start a session | Everyone |
| `check_claim_status` | Retrieve claim information | Everyone |
| `get_customer_info` | Retrieve customer information | Everyone |
| `get_policy_details` | Retrieve policy information | Everyone |
| `file_claim` | Submit a new insurance claim | Everyone |
| `approve_claim` | Approve or reject claims (Human Approval for high-value claims) | Underwriter, Risk Analyst, Admin |
| `assess_risk` | AI-assisted insurance risk assessment | Everyone |

## Roles & Approval Limits

| Role | Can Approve Claims? | Approval Limit |
|---|---|---|
| Claims Officer | No | — |
| Risk Analyst | Yes | Up to $50,000 |
| Underwriter | Yes | Up to $100,000 |
| Admin | Yes | Unlimited |

Claims exceeding $10,000 always require explicit human confirmation before approval.

## MCP Resources & Prompts

**Resources**

- `underwriting://guidelines`
- `compliance://policy`

**Prompts**

- `draft_denial_letter`

---

## Context Management Evaluation

Large Language Models have a limited context window. As conversations become longer, important information may be forgotten or the prompt may exceed the model's token limit.

To address this challenge, a dedicated Context Evaluation Framework was implemented to compare multiple context pruning strategies on realistic long-running insurance conversations.

Each strategy was evaluated using 10 long-context insurance claim scenarios containing user messages, assistant responses, and extensive tool outputs.

### Implemented Strategies

**Sliding Window**

Keeps only the most recent conversation messages.

- Advantages: Extremely fast, lowest token usage
- Disadvantages: Frequently loses important historical information.

**Observation Masking**

Masks old tool outputs while preserving the user-assistant conversation.

- Advantages: Preserves important information, very fast
- Disadvantages: Context size remains relatively large.

**Recursive Summarization**

Summarizes older conversation history using an LLM while preserving key information.

- Advantages: Excellent token reduction, retains critical information
- Disadvantages: Higher latency due to summarization.

**Zone-Based Pruning**

Divides the conversation into multiple zones: keep newest messages, mask recent tool outputs, summarize older history, remove the oldest content.

### Evaluation Metrics

- **Accuracy** — whether important information remained after pruning.
- **Remaining Tokens** — average context size after pruning.
- **Latency** — average execution time.

### Evaluation Results

| Strategy | Accuracy | Remaining Tokens | Latency (s) |
|---|---|---|---|
| Sliding Window | 0.00% | 68 | 0.000001 |
| Observation Masking | 100.00% | 283 | 0.000120 |
| Recursive Summarization | 100.00% | 131 | 0.456764 |
| Zone-Based Pruning | 0.00% | 227 | 0.300230 |

### Selected Strategy

After evaluating all four approaches across 10 realistic insurance conversations, Recursive Summarization was selected as the preferred long-context management strategy.

Although it introduces additional latency because it performs LLM-based summarization, it successfully preserved all critical information while reducing the average context size by more than 50% compared to Observation Masking.

### Running the Context Evaluation

```bash
python -m context_eval.run_evaluation
```

Example output:

```
===== Context Evaluation =====

Strategy                      Accuracy     Tokens     Latency
Sliding Window                 0.00%         68       0.000001
Observation Masking          100.00%        283       0.000120
Recursive Summarization      100.00%        131       0.456764
Zone-Based Pruning             0.00%        227       0.300230
```

### Running the Retrieval Evaluation

```bash
python retrieval_eval/evaluation.py
```

Example output:

```
| Architecture | Accuracy | Avg Tokens | Avg Latency |
|--------------|----------|------------|-------------|
| Naive        | 10/12    | 277        | 0.41s       |
| Hybrid       | 10/12    | 320        | 1.24s       |
| Agentic      | 9/12     | 328        | 16.03s      |
```

### Running Unit Tests

```bash
python -m pytest
```

Run only the Context Evaluation tests:

```bash
python -m pytest context_eval/tests/
```

Run a single test:

```bash
python -m pytest context_eval/tests/test_sliding_window.py
```

---

## Known Limitations

- Login currently verifies only the username. Password authentication is not yet implemented.
- The MCP server currently uses stdio transport, supporting a single local client.
- Recursive Summarization depends on an external LLM, which increases response latency.
- Context evaluation currently uses a fixed collection of test conversations rather than dynamically generated workloads.
- The selected context management strategy is configured manually and is not automatically chosen based on conversation length.
- The RAG corpus is currently limited to a single policy manual.
- Agentic RAG shows poor performance due to query rewriting and grading limitations.

---

## Future Improvements

**MCP**

- Support HTTP and WebSocket transport.
- Multi-user concurrent sessions.
- Stronger authentication with password hashing and JWT.
- More insurance-related MCP tools.

**Memory**

- Persistent long-term memory stored in a database.
- Automatic memory consolidation.
- Better episodic memory retrieval.
- Adaptive scratchpad management.

**Retrieval-Augmented Generation (RAG)**

- Re-ranking retrieved documents before generation.
- Incremental indexing for newly added documents.
- Support for multiple document collections.
- Better query rewriting for Agentic RAG.
- Caching of retrieval results to reduce latency.

**Context Management**

- Hybrid strategy combining Observation Masking and Recursive Summarization.
- Dynamic strategy selection based on the current context size.
- Automatic pruning when the token limit is reached.
- Better summarization prompts specialized for insurance conversations.

**AI Agent**

- Integrate the Context Evaluation framework directly into the live MCP Agent.
- Allow the agent to automatically switch between pruning strategies.
- Support continuous long conversations without exceeding the model context window.

---

## Contributors

This project was developed as part of the Memory & RAG Lab and Model Context Protocol (MCP) Lab.

Contributors worked on:

- MCP Server
- AI Agent
- Memory System
- Retrieval-Augmented Generation (RAG)
- Context Evaluation Framework
- SQL Database Design

---

## License

This project was developed for educational purposes as part of a university training program.

It is intended to demonstrate:

- Model Context Protocol (MCP)
- Long-Term Memory
- Retrieval-Augmented Generation (RAG)
- Context Management Strategies
- AI Agent Design
- Human-in-the-loop workflows

No commercial use is intended.