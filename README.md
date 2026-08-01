# Harborstone Insurance — MCP AI Agent

An AI-powered assistant for marine insurance operations, built on the **Model Context Protocol (MCP)**. Employees can check claims, look up policies, file new claims, approve high-value decisions, and run AI-assisted risk assessments — all through natural language — while every action stays under role-based access control and human oversight.

This project demonstrates a full MCP client/server implementation: a Python **MCP server** (FastMCP) exposing tools, resources, and prompts backed by a SQL Server database, and a Python **MCP agent** that connects to it, uses Google Gemini to decide which tools to call, and provides an interactive terminal chat.

## Features

- **Conversational access to company data** — ask natural-language questions about claims, policies, and customers instead of querying the database manually.
- **Role-based permissions** — Claims Officer, Underwriter, Risk Analyst, and Admin roles each see and can do only what they're authorized for. The `approve_claim` tool is dynamically enabled/disabled per session based on the logged-in user's role.
- **Human-in-the-loop approval** — any claim decision over $10,000 pauses execution and requires explicit human confirmation before anything is written to the database (MCP *elicitation*).
- **AI-assisted risk assessment** — combines deterministic underwriting rules (coverage amount, vessel type, vessel age) with an LLM-generated risk narrative (MCP *sampling*).
- **Audit logging** — logins and claim decisions are recorded to an `AuditLogs` table.
- **Read-only company resources** — underwriting guidelines and compliance policy are exposed as MCP resources the agent can reference.
- **Reusable prompt templates** — e.g. a claim-denial-letter template exposed as an MCP prompt.

## Architecture

```
User (terminal chat)
        │
        ▼
  MCP Agent (agent/agent.py)
   - Google Gemini decides which tool to call
   - Handles elicitation (human approval) and sampling (AI risk analysis)
        │  MCP protocol over stdio
        ▼
  MCP Server (mcp_server/server.py)
   - FastMCP: tools, resources, prompts
   - Role-based access control
   - Session management
        │
        ▼
  SQL Server database (HarborstoneInsurance)
```

## Tech Stack

- **Python 3.11+**
- **[FastMCP](https://gofastmcp.com)** — MCP server framework
- **MCP Python SDK** — client session, stdio transport
- **Google Gemini API** — the agent's reasoning/tool-calling model
- **SQL Server** + **pyodbc** — database and driver
- **Pydantic** — input validation
- **python-dotenv** — environment configuration

## Prerequisites

- Python 3.11 or later
- SQL Server (local or remote) with the `HarborstoneInsurance` database
- ODBC Driver 18 for SQL Server installed
- A Google Gemini API key ([Google AI Studio](https://aistudio.google.com))

## Project Structure

```
harborstone-insurance-b/
├── agent/
│   └── agent.py          # MCP client / AI agent + terminal chat
├── mcp_server/
│   └── server.py         # MCP server: tools, resources, prompts
├── .env                   # environment configuration (not committed)
└── README.md
```

## Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd harborstone-insurance-b
   ```

2. **Create a virtual environment and install dependencies**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate      # Windows
   # source .venv/bin/activate # macOS/Linux

   pip install fastmcp mcp pyodbc python-dotenv pydantic google-genai
   ```

3. **Set up the database**
   Create the `HarborstoneInsurance` SQL Server database with the required tables (`Employees`, `Customers`, `Vessels`, `InsurancePolicies`, `Claims`, `AuditLogs`).

4. **Configure environment variables**
   Create a `.env` file in the project root:
   ```env
   # Database
   WIN_DB_SERVER=localhost\SQLEXPRESS
   WIN_DB_NAME=HarborstoneInsurance
   WIN_DB_DRIVER=ODBC Driver 18 for SQL Server
   WIN_DB_AUTH_TYPE=WINDOWS          # or SQL
   # If WIN_DB_AUTH_TYPE=SQL, also set:
   # WIN_DB_USERNAME=your_username
   # WIN_DB_PASSWORD=your_password

   # MCP server transport
   TRANSPORT_TYPE=stdio

   # Gemini
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_MODEL=gemini-2.5-flash-lite
   ```

## Running the Project

The agent starts the MCP server automatically — you only need to run the agent:

```bash
python agent/agent.py
```

On startup, the agent will:
1. Launch the MCP server over stdio and complete the MCP handshake.
2. Discover available tools, resources, and prompts.
3. Prompt you to log in.
4. Start an interactive chat where you can type natural-language requests.

### Example session

```
You: check claim 1
You: show me policy 2
You: assess the risk of policy 3
You: file a claim for policy 2 for $5000 because the vessel was damaged during a storm
You: approve claim 4
```

Type `help` at any time for a full list of commands.

## Available MCP Tools

| Tool | Description | Access |
|---|---|---|
| `login` | Authenticate and start a session | Anyone |
| `check_claim_status` | Look up a claim's status and details | Anyone |
| `get_customer_info` | Look up customer details | Anyone |
| `get_policy_details` | Look up policy details | Anyone |
| `file_claim` | File a new claim | Anyone |
| `approve_claim` | Approve or deny a claim (triggers human approval above $10,000) | Underwriter, Risk Analyst, Admin |
| `assess_risk` | AI-assisted risk assessment for a policy | Anyone |

## Roles & Approval Limits

| Role | Can Approve Claims? | Limit |
|---|---|---|
| Claims Officer | No (read-only) | — |
| Risk Analyst | Yes | Up to $50,000 |
| Underwriter | Yes | Up to $100,000 |
| Admin | Yes | Unlimited |

Claims over $10,000 always require explicit human confirmation before being approved, regardless of role.

## Resources & Prompts

- **`underwriting://guidelines`** — company underwriting guidelines (read-only resource)
- **`compliance://policy`** — compliance policy (read-only resource)
- **`draft_denial_letter`** — reusable prompt template for drafting claim denial letters

## Known Limitations

- Login currently verifies the username only; password verification is not yet implemented.
- Runs over stdio (single local client) rather than a network transport.

## Future Improvements

- Real password hashing and authentication
- HTTP transport for multi-client / remote access
- Expanded fraud-detection rules
- Customer-facing self-service assistant

## License

This project was built for educational purposes as part of a training program.