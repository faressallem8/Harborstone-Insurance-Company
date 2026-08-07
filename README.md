# Harborstone Insurance — MCP AI Agent

An AI-powered assistant for marine insurance operations, built on the **Model Context Protocol (MCP)**.

Employees can check claims, retrieve policy information, file new claims, approve high-value decisions, perform AI-assisted risk assessments, and manage long conversations through intelligent context management.

This project demonstrates a complete MCP client/server implementation consisting of:

- A Python **MCP server** built with FastMCP exposing tools, resources, and prompts backed by a SQL Server database.
- A Python **MCP agent** that connects to the server, uses **Groq Llama 3** for reasoning and tool calling, and provides an interactive terminal interface.
- A **Memory & RAG module** that provides long-term memory and grounded document retrieval.
- A **Context Evaluation framework** that compares multiple long-context management strategies using realistic insurance conversations.

---

# Features

- **Conversational access to company data** — ask natural-language questions about claims, policies, customers, and underwriting information.

- **Role-based permissions** — Claims Officer, Underwriter, Risk Analyst, and Admin roles each have different permissions.

- **Human-in-the-loop approval** — claims above $10,000 require explicit human confirmation before approval.

- **AI-assisted risk assessment** — combines deterministic underwriting rules with LLM-generated explanations.

- **Audit logging** — important actions are stored inside the AuditLogs table.

- **Reusable MCP resources and prompts** — underwriting guidelines, compliance policy, and denial letter templates.

- **Memory & Retrieval-Augmented Generation (RAG)** — enables the assistant to remember previous information and retrieve company knowledge from documents.

- **Long-context management evaluation** — implements and evaluates multiple context pruning strategies for handling conversations that exceed the model context window.

- **Automated benchmarking** — compares context strategies using:
  - Accuracy
  - Remaining Tokens
  - Latency

---

# Architecture

```text
                              User
                               │
                               ▼
                   MCP Agent (agent.py)
      - Groq Llama 3 reasoning & tool calling
      - Memory integration
      - RAG retrieval
      - Context management
                               │
                 MCP Protocol over stdio
                               │
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
          ┌────────────────────┴────────────────────┐
          ▼                                         ▼
      Memory Module                           RAG Module
 Short-Term Memory                    Chroma Vector Database
 Semantic Memory                      Embeddings
 Episodic Memory                      Document Retrieval

                               │
                               ▼
                 Context Evaluation Framework

             Sliding Window
             Observation Masking
             Recursive Summarization
             Zone-Based Pruning

                     │
                     ▼

          Accuracy • Token Reduction • Latency
```

---

# Tech Stack

- Python 3.11+
- FastMCP
- MCP Python SDK
- Groq API (Llama 3)
- SQL Server
- pyodbc
- ChromaDB
- Pydantic
- python-dotenv
- Pytest

# Prerequisites

Before running the project, make sure the following requirements are installed:

- Python 3.11 or later
- SQL Server (local or remote)
- ODBC Driver 18 for SQL Server
- A Groq API Key
- Git

---

# Project Structure

```text
Harborstone-Insurance-Company/

├── agent/
│   └── agent.py

├── mcp_server/
│   └── server.py

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
│   ├── chunking.py
│   ├── embedding.py
│   ├── retriever.py
│   ├── vector_store.py
│   ├── self_rag.py
│   └── ...

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

├── chroma_db/
├── db/
├── .env
├── requirements.txt
└── README.md
```

---

# Setup

## 1. Clone the repository

```bash
git clone <your-repository-url>

cd Harborstone-Insurance-Company
```

---

## 2. Create a virtual environment

Windows

```bash
python -m venv .venv

.venv\Scripts\activate
```

Linux / macOS

```bash
source .venv/bin/activate
```

---

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure the database

Create the SQL Server database:

```
HarborstoneInsurance
```

Run the SQL scripts inside the **db/** folder:

```
create_database.sql

seed_data.sql

queries.sql
```

---

## 5. Configure environment variables

Create a `.env` file in the project root.

Example:

```env
# ===========================
# SQL Server
# ===========================

WIN_DB_SERVER=localhost\SQLEXPRESS
WIN_DB_NAME=HarborstoneInsurance
WIN_DB_DRIVER=ODBC Driver 18 for SQL Server
WIN_DB_AUTH_TYPE=WINDOWS

# If SQL Authentication is used:
# WIN_DB_USERNAME=your_username
# WIN_DB_PASSWORD=your_password

# ===========================
# MCP
# ===========================

TRANSPORT_TYPE=stdio

# ===========================
# Groq
# ===========================

GROQ_API_KEY=your_groq_api_key

GROQ_MODEL=llama-3.3-70b-versatile
```

---

# Running the Project

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
6. User login
7. Interactive AI chat begins

---

## Example Session

```text
You: check claim 4

You: get policy 7

You: assess the risk of policy 9

You: file a claim for policy 12

You: approve claim 18

You: explain why claim 5 was rejected
```

Type:

```text
help
```

at any time to display all supported commands.

# Available MCP Tools

| Tool | Description | Access |
|------|-------------|--------|
| `login` | Authenticate and start a session | Everyone |
| `check_claim_status` | Retrieve claim information | Everyone |
| `get_customer_info` | Retrieve customer information | Everyone |
| `get_policy_details` | Retrieve policy information | Everyone |
| `file_claim` | Submit a new insurance claim | Everyone |
| `approve_claim` | Approve or reject claims (Human Approval for high-value claims) | Underwriter, Risk Analyst, Admin |
| `assess_risk` | AI-assisted insurance risk assessment | Everyone |

---

# Roles & Approval Limits

| Role | Can Approve Claims? | Approval Limit |
|------|----------------------|----------------|
| Claims Officer | ❌ No | — |
| Risk Analyst | ✅ Yes | Up to \$50,000 |
| Underwriter | ✅ Yes | Up to \$100,000 |
| Admin | ✅ Yes | Unlimited |

Claims exceeding **\$10,000** always require explicit human confirmation before approval.

---

# MCP Resources & Prompts

### Resources

- `underwriting://guidelines`
- `compliance://policy`

### Prompts

- `draft_denial_letter`

---

# Context Management Evaluation

Large Language Models have a limited context window. As conversations become longer, important information may be forgotten or the prompt may exceed the model's token limit.

To address this challenge, a dedicated **Context Evaluation Framework** was implemented to compare multiple context pruning strategies on realistic long-running insurance conversations.

Each strategy was evaluated using **10 long-context insurance claim scenarios** containing user messages, assistant responses, and extensive tool outputs.

---

## Implemented Strategies

### Sliding Window

Keeps only the most recent conversation messages.

**Advantages**

- Extremely fast
- Lowest token usage

**Disadvantages**

- Frequently loses important historical information.

---

### Observation Masking

Masks old tool outputs while preserving the user-assistant conversation.

**Advantages**

- Preserves important information
- Very fast

**Disadvantages**

- Context size remains relatively large.

---

### Recursive Summarization

Summarizes older conversation history using an LLM while preserving key information.

**Advantages**

- Excellent token reduction
- Retains critical information
- Suitable for very long conversations

**Disadvantages**

- Higher latency due to summarization.

---

### Zone-Based Pruning

Divides the conversation into multiple zones:

- Keep newest messages
- Mask recent tool outputs
- Summarize older history
- Remove the oldest content

This strategy attempts to balance information preservation with token reduction.

---

# Evaluation Metrics

Each strategy was evaluated using the following metrics:

- **Accuracy** — whether important information remained after pruning.
- **Remaining Tokens** — average context size after pruning.
- **Latency** — average execution time.

---

# Evaluation Results

| Strategy | Accuracy | Remaining Tokens | Latency (s) |
|----------|---------:|-----------------:|------------:|
| Sliding Window | 0.00% | 68 | 0.000001 |
| Observation Masking | 100.00% | 283 | 0.000120 |
| Recursive Summarization | 100.00% | 131 | 0.456764 |
| Zone-Based Pruning | 0.00% | 227 | 0.300230 |

---

# Selected Strategy

After evaluating all four approaches across **10 realistic insurance conversations**, **Recursive Summarization** was selected as the preferred long-context management strategy.

Although it introduces additional latency because it performs LLM-based summarization, it successfully preserved all critical information while reducing the average context size by more than **50%** compared to Observation Masking.

Insurance claim investigations often involve lengthy conversations, repeated tool outputs, and extensive reasoning. Reducing prompt size while maintaining accuracy provides a better long-term solution than simply minimizing execution time.

---

# Running the Context Evaluation

Run the complete evaluation:

```bash
python -m context_eval.run_evaluation
```

Example output:

```text
===== Context Evaluation =====

Strategy                      Accuracy     Tokens     Latency

Sliding Window                 0.00%         68       0.000001
Observation Masking          100.00%        283       0.000120
Recursive Summarization      100.00%        131       0.456764
Zone-Based Pruning             0.00%        227       0.300230
```

---

# Running Unit Tests

Run all tests:

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

Other available tests:

```text
test_sliding_window.py

test_masking.py

test_recursive_summary.py

test_zone_pruning.py
```

These tests verify that each context management strategy behaves correctly under different long-conversation scenarios.

---

# Known Limitations

While the current implementation demonstrates the required concepts for the MCP, Memory, and RAG labs, there are still several limitations:

- Login currently verifies only the username. Password authentication is not yet implemented.
- The MCP server currently uses **stdio** transport, supporting a single local client.
- Recursive Summarization depends on an external LLM, which increases response latency.
- Context evaluation currently uses a fixed collection of test conversations rather than dynamically generated workloads.
- The selected context management strategy is configured manually and is not automatically chosen based on conversation length.

---

# Future Improvements

Several enhancements can be added in future versions of the project:

## MCP

- Support HTTP and WebSocket transport.
- Multi-user concurrent sessions.
- Stronger authentication with password hashing and JWT.
- More insurance-related MCP tools.

---

## Memory

- Persistent long-term memory stored in a database.
- Automatic memory consolidation.
- Better episodic memory retrieval.
- Adaptive scratchpad management.

---

## Retrieval-Augmented Generation (RAG)

- Hybrid keyword + semantic retrieval.
- Re-ranking retrieved documents before generation.
- Incremental indexing for newly added documents.
- Support for multiple document collections.

---

## Context Management

- Hybrid strategy combining Observation Masking and Recursive Summarization.
- Dynamic strategy selection based on the current context size.
- Automatic pruning when the token limit is reached.
- Better summarization prompts specialized for insurance conversations.
- Additional evaluation metrics such as memory usage and cost per request.

---

## AI Agent

- Integrate the Context Evaluation framework directly into the live MCP Agent.
- Allow the agent to automatically switch between pruning strategies depending on conversation length.
- Support continuous long conversations without exceeding the model context window.

---

# Contributors

This project was developed as part of the **Memory & RAG Lab** and **Model Context Protocol (MCP) Lab**.

Contributors worked on:

- MCP Server
- AI Agent
- Memory System
- Retrieval-Augmented Generation (RAG)
- Context Evaluation Framework
- SQL Database Design

---

# License

This project was developed for **educational purposes** as part of a university training program.

It is intended to demonstrate:

- Model Context Protocol (MCP)
- Long-Term Memory
- Retrieval-Augmented Generation (RAG)
- Context Management Strategies
- AI Agent Design
- Human-in-the-loop workflows

No commercial use is intended.