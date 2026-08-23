import os
import sys
import asyncio
import inspect
from pathlib import Path
from contextlib import contextmanager, asynccontextmanager
from datetime import datetime
from typing import Optional, Dict, Any, List

import pyodbc
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ConfigDict

from fastmcp import FastMCP, Context




project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))



from web_platform.database import (
    # Tool Registry
    get_all_tools as db_get_all_tools,
    register_tool as db_register_tool,
    update_tool as db_update_tool,
    delete_tool as db_delete_tool,
    get_tool_by_id as db_get_tool_by_id,
    # HITL
    create_hitl_task as db_create_hitl_task,
    resolve_hitl_task as db_resolve_hitl_task,
    # Tickets
    create_ticket as db_create_ticket,
    resolve_ticket as db_resolve_ticket,
    # Checkpoints
    save_checkpoint as db_save_checkpoint,
    get_checkpoint as db_get_checkpoint,
    get_latest_checkpoint as db_get_latest_checkpoint,
)

load_dotenv()

# ============================================================
# PYDANTIC MODELS
# ============================================================

class LoginInput(BaseModel):
    """Login credentials"""
    username: str = Field(min_length=3, max_length=50, description="Username")
    password: str = Field(min_length=1, description="Password")
    model_config = ConfigDict(extra="forbid")


class FileClaimInput(BaseModel):
    """Input for filing a claim"""
    policy_id: int = Field(ge=1, description="Policy ID")
    amount: float = Field(gt=0, description="Claim amount in USD")
    description: str = Field(min_length=10, max_length=500, description="Claim description")
    model_config = ConfigDict(extra="forbid")


class ApproveClaimInput(BaseModel):
    """Input for approving a claim"""
    claim_id: int = Field(ge=1, description="Claim ID")
    decision: str = Field(pattern="^(approved|denied)$", description="Decision")
    notes: Optional[str] = Field(None, max_length=500, description="Notes")
    model_config = ConfigDict(extra="forbid")


class ClaimApprovalConfirmation(BaseModel):
    """Schema for the human confirmation requested via ctx.elicit() for high-value claims"""
    confirm: str = Field(description="Do you confirm this decision? Answer 'yes' or 'no'")
    reasoning: str = Field(description="Please explain your reasoning")


class CheckClaimInput(BaseModel):
    """Input for checking claim status"""
    claim_id: int = Field(ge=1, description="Claim ID")
    model_config = ConfigDict(extra="forbid")


class AssessRiskInput(BaseModel):
    """Input for risk assessment"""
    policy_id: int = Field(ge=1, description="Policy ID")
    model_config = ConfigDict(extra="forbid")


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_connection_string() -> str:
    """Build SQL Server connection string from environment variables"""
    server = os.getenv("WIN_DB_SERVER", "localhost\\SQLEXPRESS")
    database = os.getenv("WIN_DB_NAME", "HarborstoneInsurance")
    driver = os.getenv("WIN_DB_DRIVER", "ODBC Driver 18 for SQL Server")
    auth_type = os.getenv("WIN_DB_AUTH_TYPE", "WINDOWS")

    if auth_type.upper() == "WINDOWS":
        return (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )
    else:
        username = os.getenv("WIN_DB_USERNAME", "")
        password = os.getenv("WIN_DB_PASSWORD", "")
        return (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            f"UID={username};"
            f"PWD={password};"
            "TrustServerCertificate=yes;"
        )


@contextmanager
def get_db():
    """Database connection context manager for SQL Server"""
    conn_str = get_connection_string()
    conn = pyodbc.connect(conn_str)
    try:
        yield conn
    finally:
        conn.close()


def row_to_dict(cursor, row):
    """Convert a pyodbc row to dict using cursor.description."""
    if row is None:
        return None
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def rows_to_dicts(cursor, rows):
    """Same as row_to_dict, but for a list of rows."""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def test_connection():
    """Test database connection"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()
            print(f"[OK] Connected to SQL Server: {version[0][:50]}...")

            cursor.execute("SELECT COUNT(*) FROM Employees")
            count = cursor.fetchone()[0]
            print(f"[OK] Employees count: {count}")
            return True
    except Exception as e:
        print(f"[ERROR] Failed to connect to SQL Server: {e}")
        return False


# ============================================================
# LIFESPAN (Startup/Shutdown)
# ============================================================

async def init_mcp_registry():
    """Initialize the tool registry."""
    await tool_registry.initialize()
    print(f"[MCP] Registry initialized with {len(tool_registry.tools_cache)} agents")
    
    for agent, tools in tool_registry.tools_cache.items():
        enabled = [name for name, enabled in tools.items() if enabled]
        if enabled:
            print(f"  - {agent}: {', '.join(enabled)}")


@asynccontextmanager
async def lifespan(server_instance):
    """Lifespan context manager for startup/shutdown events."""
    print("🚀 Starting MCP Server...")
    await init_mcp_registry()
    try:
        yield
    finally:
        print("👋 Shutting down MCP Server...")


# ============================================================
# FAST MCP SERVER INSTANCE (with lifespan)
# ============================================================

server = FastMCP(
    "Harborstone Insurance Server",
    lifespan=lifespan,
)

current_session = {}


# ============================================================
# MCP RESOURCES
# ============================================================

@server.resource("underwriting://guidelines")
def get_guidelines() -> str:
    """Underwriting guidelines - read-only resource"""
    return """UNDERWRITING GUIDELINES - HARBORSTONE INSURANCE

    Approval Limits by Role:
    - Claims Officer: Cannot approve claims (read-only)
    - Underwriter: Can approve claims up to $100,000
    - Risk Analyst: Can approve claims up to $50,000
    - Admin: Can approve any amount

    High-Value Claims:
    - Claims > $10,000: Require human approval (elicitation)
    - Claims > $50,000: Require Underwriter or Admin
    - Claims > $100,000: Require Admin approval

    Fraud Indicators:
    - Multiple claims in short time
    - Claim amount suspiciously high
    - Inconsistent documentation

    Processing Standards:
    - All claims must be processed within 30 days
    - Documentation must be complete
    - All decisions must be logged
    """


@server.resource("compliance://policy")
def get_policy() -> str:
    """Compliance policy - read-only resource"""
    return """COMPLIANCE POLICY - HARBORSTONE INSURANCE

    Data Protection:
    - Customer PII must be protected
    - No sharing of data without consent
    - All breaches reported within 24 hours

    Claims Processing:
    - All claims documented
    - Decisions must be justified
    - Appeals process available

    Audit Requirements:
    - All actions logged
    - Regular compliance reviews
    - Staff training required
    """


@server.prompt
def draft_denial_letter(claim_id: int, reason: str) -> str:
    """Template for claim denial letters"""
    return f"""CLAIM DENIAL LETTER - HARBORSTONE INSURANCE

Draft a formal denial letter for claim #{claim_id}.

Reason for Denial: {reason}

Requirements:
1. Professional and empathetic tone
2. Clear explanation of why claim was denied
3. Reference specific policy sections
4. Include appeal instructions
5. Include contact information

The letter should be ready for a manager's signature.
"""


# ============================================================
# REAL MCP TOOLS
# ============================================================

@server.tool
async def login(username: str, password: str, ctx: Context) -> str:
    """Authenticate user and create session"""
    global current_session

    privileged_roles = {"Underwriter", "Admin", "Risk Analyst"}

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT employee_id, username, role_name, full_name
            FROM employees
            WHERE username = ? AND is_active = 1
        """, (username,))
        user = row_to_dict(cursor, cursor.fetchone())

        if not user:
            return "ERROR: Invalid username or inactive account"

        current_session = {
            "user_id": user["employee_id"],
            "username": user["username"],
            "role": user["role_name"],
            "full_name": user["full_name"],
            "session_id": ctx.session_id,
        }

        if user["role_name"] in privileged_roles:
            await ctx.enable_components(names={"approve_claim"}, components={"tool"})
            tools_list = "check_claim_status, get_customer_info, get_policy_details, file_claim, assess_risk, approve_claim"
        else:
            await ctx.disable_components(names={"approve_claim"}, components={"tool"})
            tools_list = "check_claim_status, get_customer_info, get_policy_details, file_claim, assess_risk"

        cursor.execute("""
            INSERT INTO AuditLogs (employee_id, action, table_name, record_id)
            VALUES (?, 'LOGIN', 'employee', ?)
        """, (user["employee_id"], user["employee_id"]))
        conn.commit()

    return f"""LOGIN SUCCESSFUL

    User: {user['full_name']} ({user['username']})
    Role: {user['role_name'].upper()}
    Session: {ctx.session_id[:20]}...

    Available Tools:
    {tools_list}

    A tools/list_changed notification has been sent to your client."""


@server.tool
async def check_claim_status(claim_id: int) -> str:
    """Check the status of a claim."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                c.claim_id,
                c.claim_number,
                c.claim_amount,
                c.status,
                c.description,
                c.claim_date,
                c.priority,
                c.risk_level,
                p.policy_number,
                cust.full_name as customer_name,
                e.full_name as assigned_to
            FROM Claims c
            JOIN InsurancePolicies p ON c.policy_id = p.policy_id
            JOIN Customers cust ON p.customer_id = cust.customer_id
            LEFT JOIN Employees e ON c.assigned_employee_id = e.employee_id
            WHERE c.claim_id = ?
        """, (claim_id,))
        claim = row_to_dict(cursor, cursor.fetchone())

        if not claim:
            return "ERROR: Claim not found"

    return f"""CLAIM STATUS REPORT

    Claim ID: {claim['claim_id']}
    Claim Number: {claim['claim_number']}
    Customer: {claim['customer_name']}
    Policy: {claim['policy_number']}
    Amount: ${claim['claim_amount']:,.2f}
    Status: {claim['status']}
    Priority: {claim['priority']}
    Risk Level: {claim['risk_level']}
    Description: {claim['description']}
    Filed: {claim['claim_date']}
    Assigned To: {claim['assigned_to'] or 'Unassigned'}"""


@server.tool
async def get_customer_info(customer_id: int) -> str:
    """Get customer information (read-only)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                customer_id,
                customer_code,
                full_name,
                email,
                phone,
                city,
                country,
                status
            FROM Customers 
            WHERE customer_id = ?
        """, (customer_id,))
        customer = row_to_dict(cursor, cursor.fetchone())

        if not customer:
            return "ERROR: Customer not found"

    return f"""CUSTOMER INFORMATION

    ID: {customer['customer_id']}
    Code: {customer['customer_code']}
    Name: {customer['full_name']}
    Email: {customer['email']}
    Phone: {customer['phone']}
    City: {customer['city']}
    Country: {customer['country']}
    Status: {customer['status']}"""


@server.tool
async def get_policy_details(policy_id: int) -> str:
    """Get policy details (read-only)."""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                p.policy_id,
                p.policy_number,
                p.policy_type,
                p.coverage_amount,
                p.deductible,
                p.premium,
                p.start_date,
                p.end_date,
                p.status,
                cust.full_name as customer_name,
                v.vessel_name
            FROM InsurancePolicies p
            JOIN Customers cust ON p.customer_id = cust.customer_id
            JOIN Vessels v ON p.vessel_id = v.vessel_id
            WHERE p.policy_id = ?
        """, (policy_id,))
        policy = row_to_dict(cursor, cursor.fetchone())

        if not policy:
            return "ERROR: Policy not found"

    return f"""POLICY DETAILS

    Policy ID: {policy['policy_id']}
    Policy Number: {policy['policy_number']}
    Customer: {policy['customer_name']}
    Vessel: {policy['vessel_name']}
    Type: {policy['policy_type'] or 'N/A'}
    Coverage: ${policy['coverage_amount']:,.2f}
    Deductible: ${policy['deductible']:,.2f}
    Premium: ${policy['premium']:,.2f}
    Start Date: {policy['start_date']}
    End Date: {policy['end_date']}
    Status: {policy['status'].upper()}"""


@server.tool
async def file_claim(
    policy_id: int,
    amount: float,
    description: str,
    ctx: Context,
    incident_date: str = ""
) -> str:
    """File a new claim."""
    global current_session

    await ctx.report_progress(0, 100, "Starting claim filing...")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT policy_id FROM InsurancePolicies WHERE policy_id = ?", (policy_id,))
        if not cursor.fetchone():
            return "ERROR: Policy not found"

    await ctx.report_progress(30, 100, "Generating claim number...")

    claim_number = f"CLM-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    await ctx.report_progress(60, 100, "Creating claim record...")

    user_id = current_session.get("user_id") if current_session else None
    incident_date_value = incident_date.strip() or datetime.now().strftime("%Y-%m-%d")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Claims 
            (policy_id, claim_number, claim_amount, description, status, assigned_employee_id, incident_date)
            VALUES (?, ?, ?, ?, 'Pending', ?, ?)
        """, (policy_id, claim_number, amount, description, user_id, incident_date_value))
        conn.commit()

        cursor.execute("SELECT SCOPE_IDENTITY()")
        claim_id = cursor.fetchone()[0]

    await ctx.report_progress(100, 100, "Claim filed successfully!")

    return f"""CLAIM FILED

    Claim ID: {claim_id}
    Claim Number: {claim_number}
    Amount: ${amount:,.2f}
    Status: Pending Review
    Description: {description}"""


@server.tool
async def approve_claim(
    claim_id: int,
    decision: str,
    ctx: Context,
    notes: str = ""
) -> str:
    """Approve or deny a claim."""
    global current_session

    await ctx.report_progress(0, 100, "Starting claim approval...")

    if not current_session:
        return "ERROR: Please login first"

    role = current_session["role"]
    user_id = current_session["user_id"]

    await ctx.report_progress(20, 100, f"Checking authorization for {role}...")

    if role not in ["Underwriter", "Admin", "Risk Analyst"]:
        return f"ERROR: {role} cannot approve claims. Requires Underwriter, Risk Analyst, or Admin."

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT claim_amount, status
            FROM Claims 
            WHERE claim_id = ?
        """, (claim_id,))
        claim = row_to_dict(cursor, cursor.fetchone())

        if not claim:
            return "ERROR: Claim not found"

        if claim["status"] != "Pending":
            return f"ERROR: Claim already {claim['status']}"

        amount = claim["claim_amount"]

        await ctx.report_progress(40, 100, f"Claim amount: ${amount:,.2f}")

        if role == "Risk Analyst" and amount > 50000:
            return f"ERROR: Risk Analysts can only approve up to $50,000. This claim is ${amount:,.2f}."

        if role == "Underwriter" and amount > 100000:
            return f"ERROR: Underwriters can only approve up to $100,000. This claim is ${amount:,.2f}."

        reasoning = ""

        if amount > 10000:
            await ctx.report_progress(50, 100, "High-value claim - requesting human approval...")

            response = await ctx.elicit(
                message=f"""High-Value Claim Approval Required

                Claim #{claim_id} requires your approval.

                Amount: ${amount:,.2f}
                Decision: {decision}
                Notes: {notes or 'None provided'}

                This claim exceeds the $10,000 automatic approval limit.
                Please confirm this decision.""",
                response_type=ClaimApprovalConfirmation,
            )

            if response.action == "decline":
                return f"Claim {decision} declined by human reviewer."
            if response.action == "cancel":
                return f"Claim {decision} cancelled by human reviewer."
            if response.action != "accept":
                return f"ERROR: Unexpected elicitation response: {response.action}"

            confirmation = response.data
            if confirmation.confirm.strip().lower() != "yes":
                return f"Claim {decision} cancelled by human.\n\nReason: {confirmation.reasoning or 'No reason provided'}"

            reasoning = confirmation.reasoning
            await ctx.report_progress(70, 100, f"Human confirmed: {reasoning[:50]}...")
        else:
            await ctx.report_progress(60, 100, "Claim under $10,000 - auto-approved")

        await ctx.report_progress(80, 100, "Processing decision...")

        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE Claims 
                SET status = ?, assigned_employee_id = ?
                WHERE claim_id = ?
            """, (decision.capitalize(), user_id, claim_id))
            conn.commit()

            cursor.execute("""
                INSERT INTO AuditLogs (employee_id, action, table_name, record_id)
                VALUES (?, 'CLAIM_APPROVED', 'Claims', ?)
            """, (user_id, claim_id))
            conn.commit()

        await ctx.report_progress(100, 100, "Claim processed!")

        result = f"""CLAIM {decision.upper()}!

        Claim ID: {claim_id}
        Decision: {decision.upper()}
        Amount: ${amount:,.2f}
        Notes: {notes or 'None'}
        """
        if amount > 10000 and reasoning:
            result += f"Human Reasoning: {reasoning}\n"
        result += "\nThe customer will be notified."

        return result


@server.tool
async def assess_risk(policy_id: int, ctx: Context) -> str:
    """Assess risk for a policy using sampling."""
    await ctx.report_progress(0, 100, "Starting risk assessment...")

    await ctx.report_progress(20, 100, "Fetching policy details...")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                p.policy_number,
                p.policy_type,
                p.coverage_amount,
                p.status,
                cust.full_name as customer_name,
                v.vessel_name,
                v.vessel_type,
                v.year_built,
                v.insured_value
            FROM InsurancePolicies p
            JOIN Customers cust ON p.customer_id = cust.customer_id
            JOIN Vessels v ON p.vessel_id = v.vessel_id
            WHERE p.policy_id = ?
        """, (policy_id,))
        policy = row_to_dict(cursor, cursor.fetchone())

        if not policy:
            return "ERROR: Policy not found"

        await ctx.report_progress(40, 100, "Analyzing policy data...")

        risk_factors = []
        risk_score = "Low"
        current_year = datetime.now().year

        if policy["coverage_amount"] > 250000:
            risk_score = "High"
            risk_factors.append("High coverage amount increases risk exposure")
        elif policy["coverage_amount"] > 100000:
            risk_score = "Medium"
            risk_factors.append("Moderate coverage amount")

        if policy["vessel_type"]:
            vessel_type = policy["vessel_type"]
            if "Fishing" in vessel_type:
                risk_score = "Medium" if risk_score == "Low" else risk_score
                risk_factors.append("Fishing vessels have higher operational risk")
            elif "Tanker" in vessel_type:
                risk_score = "High"
                risk_factors.append("Tankers have environmental liability risk")

        if policy["year_built"]:
            vessel_age = current_year - policy["year_built"]
            if vessel_age > 20:
                risk_factors.append(f"Vessel is {vessel_age} years old - age factor")
            elif vessel_age > 10:
                risk_factors.append(f"Vessel is {vessel_age} years old - moderate age factor")

        await ctx.report_progress(60, 100, "Requesting AI analysis...")

        ai_analysis = await ctx.sample(
            messages=f"""Analyze this marine insurance policy risk:

            Policy Number: {policy['policy_number']}
            Type: {policy['policy_type'] or 'N/A'}
            Coverage Amount: ${policy['coverage_amount']:,.2f}
            Customer: {policy['customer_name']}
            Vessel: {policy['vessel_name']} ({policy['vessel_type'] or 'N/A'})
            Year Built: {policy['year_built']}
            Insured Value: ${policy['insured_value']:,.2f}
            Risk Factors: {', '.join(risk_factors) if risk_factors else 'None identified'}

            Provide:
            1. Overall risk level (Low/Medium/High)
            2. Key risk factors
            3. Recommendations for underwriting
            4. Any red flags to investigate

            Keep it concise and professional."""
        )

        await ctx.report_progress(80, 100, "Generating report...")

        await ctx.report_progress(100, 100, "Assessment complete!")

        return f"""RISK ASSESSMENT REPORT - HARBORSTONE INSURANCE

Policy: {policy['policy_number']}
Customer: {policy['customer_name']}
Vessel: {policy['vessel_name']}

Overall Risk: {risk_score}

Risk Factors:
{chr(10).join(f'- {factor}' for factor in risk_factors) if risk_factors else '- None identified'}

Coverage Amount: ${policy['coverage_amount']:,.2f}
Vessel Age: {current_year - policy['year_built'] if policy['year_built'] else 'N/A'} years
Policy Status: {policy['status'].upper()}

AI Analysis:
{ai_analysis.text if hasattr(ai_analysis, "text") else ai_analysis}

Recommendation: {"Proceed with caution - requires review" if risk_score == "High" else "Proceed with normal underwriting process"}"""


# ============================================================
# DEFAULT VISIBILITY - approve_claim is privileged
# ============================================================

server.disable(names={"approve_claim"}, components={"tool"})


# ============================================================
# TOOL HANDLERS MAP (Real MCP functions only)
# ============================================================

TOOL_HANDLERS = {
    "login": login,
    "check_claim_status": check_claim_status,
    "get_customer_info": get_customer_info,
    "get_policy_details": get_policy_details,
    "file_claim": file_claim,
    "approve_claim": approve_claim,
    "assess_risk": assess_risk,
}


# ============================================================
# DYNAMIC TOOL REGISTRY
# ============================================================

class MCPToolRegistry:
    """
    Dynamic tool registry that syncs with the database.
    Admin controls tool permissions from the web UI.
    """
    
    def __init__(self):
        self.tools_cache = {}  # {agent_name: {tool_name: enabled}}
        self._initialized = False
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Load tools from database on startup."""
        if self._initialized:
            return
        
        async with self._lock:
            if self._initialized:
                return
            
            tools = db_get_all_tools()
            for tool in tools:
                agent = tool['agent_name']
                if agent not in self.tools_cache:
                    self.tools_cache[agent] = {}
                self.tools_cache[agent][tool['tool_name']] = tool['enabled']
            
            self._initialized = True
            print(f"[MCP] Loaded tools for {len(self.tools_cache)} agents")
    
    async def refresh(self):
        """Refresh tools from database."""
        async with self._lock:
            tools = db_get_all_tools()
            new_cache = {}
            for tool in tools:
                agent = tool['agent_name']
                if agent not in new_cache:
                    new_cache[agent] = {}
                new_cache[agent][tool['tool_name']] = tool['enabled']
            
            self.tools_cache = new_cache
            print(f"[MCP] Refreshed tools for {len(self.tools_cache)} agents")
    
    def get_tools_for_agent(self, agent_name: str) -> List[str]:
        """Get enabled tool names for an agent."""
        agent_tools = self.tools_cache.get(agent_name, {})
        return [name for name, enabled in agent_tools.items() if enabled]
    
    def is_tool_enabled(self, agent_name: str, tool_name: str) -> bool:
        """Check if a tool is enabled for an agent."""
        agent_tools = self.tools_cache.get(agent_name, {})
        return agent_tools.get(tool_name, False)
    
    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool exists in any agent's registry."""
        return any(
            tool_name in tools
            for tools in self.tools_cache.values()
        )


# ============================================================
# Create registry instance
# ============================================================

tool_registry = MCPToolRegistry()


# ============================================================
# MCP TOOL FUNCTIONS 
# ============================================================

async def list_tools(agent_name: str = None) -> List[Dict]:
    """
    Get list of available tools for an agent.
    If agent_name is provided, returns only tools enabled for that agent.
    """
    if agent_name:
        tool_names = tool_registry.get_tools_for_agent(agent_name)
        return [
            {
                "name": name,
                "description": TOOL_HANDLERS[name].__doc__ or f"Tool: {name}",
                "inputSchema": {},
            }
            for name in tool_names
            if name in TOOL_HANDLERS
        ]
    
    all_tools = []
    for agent, tools in tool_registry.tools_cache.items():
        for name, enabled in tools.items():
            if enabled and name in TOOL_HANDLERS:
                all_tools.append({
                    "name": name,
                    "agent": agent,
                    "description": TOOL_HANDLERS[name].__doc__ or f"Tool: {name}",
                    "inputSchema": {},
                })
    return all_tools


async def call_tool(
    agent_name: str,
    tool_name: str,
    arguments: dict,
    ctx: Optional[Context] = None,
) -> Dict:
    """
    Execute a real MCP tool for a specific agent.
    The registry controls authorization, while the actual
    MCP tool implementation performs the operation.
    """
    # 1. Check registry permission
    if not tool_registry.is_tool_enabled(agent_name, tool_name):
        return {
            "status": "error",
            "error": (
                f"Tool '{tool_name}' is not enabled "
                f"for agent '{agent_name}'"
            ),
        }
    
    # 2. Get handler - try TOOL_HANDLERS first, then module
    handler = TOOL_HANDLERS.get(tool_name)
    
    # If not found, try to get from the module directly (for testing)
    if handler is None:
        import mcp_server.server as mcp_module
        handler = getattr(mcp_module, 'TOOL_HANDLERS', {}).get(tool_name)
    
    if handler is None:
        return {
            "status": "error",
            "error": f"No handler found for tool '{tool_name}'",
        }
    
    # 3. Execute the real MCP function
    try:
        kwargs = dict(arguments)
        
        # Check if handler expects a Context parameter
        signature = inspect.signature(handler)
        if "ctx" in signature.parameters:
            if ctx is None:
                from unittest.mock import MagicMock
                ctx = MagicMock()
                ctx.session_id = "test_session"
            kwargs["ctx"] = ctx
        
        result = await handler(**kwargs)
        
        return {
            "status": "success",
            "result": result,
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }



async def get_agent_tools(agent_name: str) -> List[str]:
    """Get all enabled tool names for an agent."""
    return tool_registry.get_tools_for_agent(agent_name)


def get_all_enabled_tools() -> Dict[str, List[str]]:
    """Get all enabled tools grouped by agent."""
    result = {}
    for agent, tools in tool_registry.tools_cache.items():
        enabled = [name for name, enabled in tools.items() if enabled]
        if enabled:
            result[agent] = enabled
    return result


# ============================================================
# Admin Functions 
# ============================================================

async def admin_register_tool(tool_name: str, agent_name: str, enabled: bool = True):
    """Register a tool for an agent (called from admin UI)."""
    if tool_name not in TOOL_HANDLERS:
        return {'error': f"Tool '{tool_name}' not found in TOOL_HANDLERS"}
    
    result = db_register_tool(tool_name, agent_name, enabled)
    await tool_registry.refresh()
    return result


async def admin_update_tool(tool_id: int, enabled: bool):
    """Update tool status (called from admin UI)."""
    tool = db_get_tool_by_id(tool_id)
    if not tool:
        return {'error': 'Tool not found'}
    
    result = db_update_tool(tool_id, enabled)
    await tool_registry.refresh()
    return result


async def admin_delete_tool(tool_id: int):
    """Delete a tool (called from admin UI)."""
    success = db_delete_tool(tool_id)
    await tool_registry.refresh()
    return success


async def admin_get_agent_tools(agent_name: str) -> List[str]:
    """Get all enabled tools for an agent from the registry."""
    return tool_registry.get_tools_for_agent(agent_name)


# ============================================================
# Platform Functions (called from state graphs)
# ============================================================

def platform_create_hitl(graph_name: str, run_id: str, node_name: str,
                         state: Dict, assigned_to: str = None, 
                         priority: str = 'medium') -> Dict:
    """Create a HITL task (called from state graph)."""
    return db_create_hitl_task(graph_name, run_id, node_name, state, 
                               assigned_to, priority)


def platform_resolve_hitl(task_id: int, decision: Dict, status: str = 'resolved') -> Dict:
    """Resolve a HITL task."""
    return db_resolve_hitl_task(task_id, decision, status)


def platform_create_ticket(graph_name: str, run_id: str, node_name: str,
                           state: Dict, error_message: str,
                           error_type: str = None,
                           assigned_to: str = None,
                           severity: str = 'medium') -> Dict:
    """Create a ticket (called from state graph)."""
    return db_create_ticket(graph_name, run_id, node_name, state, 
                           error_message, error_type, assigned_to, severity)


def platform_resolve_ticket(ticket_id: int, status: str, resolution_notes: str) -> Dict:
    """Resolve a ticket."""
    return db_resolve_ticket(ticket_id, status, resolution_notes)


def platform_save_checkpoint(graph_name: str, run_id: str, node_name: str,
                             state: Dict) -> Dict:
    """Save a checkpoint (called from state graph)."""
    return db_save_checkpoint(graph_name, run_id, node_name, state)


def platform_get_checkpoint(graph_name: str, run_id: str, node_name: str) -> Optional[Dict]:
    """Get a specific checkpoint."""
    return db_get_checkpoint(graph_name, run_id, node_name)


def platform_get_latest_checkpoint(graph_name: str, run_id: str) -> Optional[Dict]:
    """Get the latest checkpoint for a run."""
    return db_get_latest_checkpoint(graph_name, run_id)


# ============================================================
# RUN - Only if not in test mode
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print("HARBORSTONE INSURANCE MCP SERVER")
    print("=" * 50)
    print()

    print("Testing database connection...")
    if not test_connection():
        print("ERROR: Database connection failed. Exiting.")
        exit(1)

    print()
    transport = os.getenv('TRANSPORT_TYPE', "stdio")
    print(f"[OK] Starting Harborstone Insurance Server with {transport} transport...")
    print()
    
    server.run(transport=transport)