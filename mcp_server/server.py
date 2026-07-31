
import os
import pyodbc
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Dict, Any, List
import mcp
from fastmcp import FastMCP, Context
from dotenv import load_dotenv

from pydantic import BaseModel, Field, ConfigDict
load_dotenv()


def get_connection_string() -> str:
    """Build SQL Server connection string from environment variables"""
    server = os.getenv("WIN_DB_SERVER", "localhost\\SQLEXPRESS")
    database = os.getenv("WIN_DB_NAME", "HarborstoneInsurance")
    driver = os.getenv("WIN_DB_DRIVER", "SQL Server")
    auth_type = os.getenv("WIN_DB_AUTH_TYPE", "WINDOWS")

    if auth_type.upper() == "WINDOWS":
        return f"DRIVER={driver};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
    else:
        username = os.getenv("WIN_DB_USERNAME", "")
        password = os.getenv("WIN_DB_PASSWORD", "")
        return f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};"


@contextmanager
def get_db():
    """Database connection context manager for SQL Server"""
    conn_str = get_connection_string()
    conn = pyodbc.connect(conn_str)
    try:
        yield conn
    finally:
        conn.close()


def test_connection():
    """Test database connection"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()
            print(f"[OK] Connected to SQL Server: {version[0][:50]}...")

            # Check if data exists
            cursor.execute("SELECT COUNT(*) FROM Employees")
            count = cursor.fetchone()[0]
            print(f"[OK] Employees count: {count}")
            return True
    except Exception as e:
        print(f"[ERROR] Failed to connect to SQL Server: {e}")
        return False

class LoginInput(BaseModel):
    """Login credentials"""
    username: str = Field( min_length=3, max_length=50, description="Username")
    password: str = Field( min_length=1, description="Password")
    model_config = ConfigDict(extra="forbid")

class FileClaimInput(BaseModel):
    """Input for filing a claim"""
    policy_id: int = Field( ge=1, description="Policy ID")
    amount: float = Field( gt=0, description="Claim amount in USD")
    description: str = Field( min_length=10, max_length=500, description="Claim description")
    model_config = ConfigDict(extra="forbid")

class ApproveClaimInput(BaseModel):
    """Input for approving a claim"""
    claim_id: int = Field( ge=1, description="Claim ID")
    decision: str = Field( pattern="^(approved|denied)$", description="Decision")
    notes: Optional[str] = Field(None, max_length=500, description="Notes")
    model_config = ConfigDict(extra="forbid")

class CheckClaimInput(BaseModel):
    """Input for checking claim status"""
    claim_id: int = Field( ge=1, description="Claim ID")
    model_config = ConfigDict(extra="forbid")

class AssessRiskInput(BaseModel):
    """Input for risk assessment"""
    policy_id: int = Field( ge=1, description="Policy ID")
    model_config = ConfigDict(extra="forbid")

server = FastMCP("Harborstone Insurance Server")

current_session = {}

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

@server.tool
async def login(username: str, password: str, ctx: Context) -> str:
    """Authenticate user and create session
    Triggers tools/list_changed notification based on role"""

    global current_session
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        SELECT employee_id, username, role_name, full_name
        FROM employees
        WHERE username = ? AND is_active = 1
        """, (username,))
        user = cursor.fetchone()

        if not user:
            return f"User {username} not found."

    # ============================================================
    # SESSION + NOTIFICATIONS: role determines which tools are visible.
    # approve_claim is disabled globally by default (see server.disable(...)
    # near the bottom of this file). Logging in as a privileged role
    # enables it for THIS session only, which fires a session-scoped
    # notifications/tools/list_changed the client can react to.
    # Logging in as a non-privileged role explicitly re-disables it, so
    # re-login as a different role on the same connection is handled too.
    # ============================================================
    privileged_roles = {"Underwriter", "Admin", "Risk Analyst"}

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

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO AuditLogs (employee_id, action, table_name, record_id)
        VALUES (?,"LOGIN",'employee',?)
        """,(user["employee_id"], user["employee_id"]))

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
    """
    Check the status of a claim.
    Anyone can check status (read-only).
    """

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
        claim = cursor.fetchone()

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
        customer = cursor.fetchone()

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
        policy = cursor.fetchone()

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
async def file_claim(policy_id: int, amount: float, description: str, ctx: Context) -> str:
    """
    File a new claim.
    Anyone can file a claim (read-only access).
    """
    global current_session


        # ============================================================
        # PROGRESS TRACKING: Shows progress to the user
        # ============================================================
    await ctx.report_progress(0, 100, "Starting claim filing...")

        # Validate policy exists
    with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT policy_id FROM InsurancePolicies WHERE policy_id = ?", (policy_id,))
            if not cursor.fetchone():
                return "ERROR: Policy not found"

    await ctx.report_progress(30, 100, "Generating claim number...")

        # Generate claim number
    claim_number = f"CLM-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    await ctx.report_progress(60, 100, "Creating claim record...")

    user_id = current_session.get("user_id") if current_session else None

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
                INSERT INTO Claims 
                (policy_id, claim_number, claim_amount, description, status, assigned_employee_id)
                VALUES (?, ?, ?, ?, 'Pending', ?)
            """, (policy_id, claim_number, amount, description, user_id))
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
async def approve_claim(claim_id: int, decision: str, ctx: Context, notes: str = "") -> str:
    """
    Approve or deny a claim.
    Requires Underwriter, Risk Analyst, or Admin role.
    High-value claims (> $10,000) trigger elicitation (human approval).
    """
    global current_session


    await ctx.report_progress(0, 100, "Starting claim approval...")


    if not current_session:
        return "ERROR: Please login first"

    role = current_session["role"]
    user_id = current_session["user_id"]

    await ctx.report_progress(20, 100, f"Checking authorization for {role}...")

    if role not in ["Underwriter", "Admin", "Risk Analyst"]:
        return f"ERROR: {role} cannot approve claims. Requires Underwriter, Risk Analyst, or Admin."

        # Get claim details
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
                SELECT claim_amount, status
                FROM Claims 
                WHERE claim_id = ?
            """, (claim_id,))
        claim = cursor.fetchone()

        if not claim:
            return "ERROR: Claim not found"

        if claim["status"] != "Pending":
            return f"ERROR: Claim already {claim['status']}"

        amount = claim["claim_amount"]

        await ctx.report_progress(40, 100, f"Claim amount: ${amount:,.2f}")

        # Role-based limits (Defensive Design)
        if role == "Risk Analyst" and amount > 50000:
            return f"ERROR: Risk Analysts can only approve up to $50,000. This claim is ${amount:,.2f}."

        if role == "Underwriter" and amount > 100000:
            return f"ERROR: Underwriters can only approve up to $100,000. This claim is ${amount:,.2f}."

        reasoning = ""

        if amount > 10000:
            await ctx.report_progress(50, 100, "High-value claim - requesting human approval...")

            response = await ctx.elicit(
                title="High-Value Claim Approval Required",
                prompt=f"""**Claim #{claim_id}** requires your approval.

                Amount: ${amount:,.2f}
                Decision: {decision}
                Notes: {notes or 'None provided'}
                
                This claim exceeds the $10,000 automatic approval limit.
                Please confirm this decision.""",
                schema={
                    "type": "object",
                    "properties": {
                        "confirm": {
                            "type": "string",
                            "enum": ["yes", "no"],
                            "description": "Do you confirm this decision?"
                        },
                        "reasoning": {
                            "type": "string",
                            "description": "Please explain your reasoning"
                        }
                    },
                    "required": ["confirm", "reasoning"],
                    "additionalProperties": False
                }
            )

            if response.get("confirm") != "yes":
                return f"Claim {decision} cancelled by human.\n\nReason: {response.get('reasoning', 'No reason provided')}"

            reasoning = response.get("reasoning", "")
            await ctx.report_progress(70, 100, f"Human confirmed: {reasoning[:50]}...")
        else:
            await ctx.report_progress(60, 100, "Claim under $10,000 - auto-approved")

        await ctx.report_progress(80, 100, "Processing decision...")

        # Update claim
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE Claims 
                SET status = ?, assigned_employee_id = ?
                WHERE claim_id = ?
            """, (decision.capitalize(), user_id, claim_id))
            conn.commit()

            # Log the action (Audit Log)
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
    """
    Assess risk for a policy using sampling.
    Calls the client's LLM for AI analysis (SAMPLING protocol concern).
    """
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
        policy = cursor.fetchone()

        if not policy:
            return "ERROR: Policy not found"

        await ctx.report_progress(40, 100, "Analyzing policy data...")

        # Calculate basic risk factors
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
            prompt=f"""Analyze this marine insurance policy risk:

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
{ai_analysis}

Recommendation: {"Proceed with caution - requires review" if risk_score == "High" else "Proceed with normal underwriting process"}"""


# NOTIFICATIONS: approve_claim is a privileged write tool, so it stays hidden
# for every connection by default. login() enables it per-session for
# Underwriter/Risk Analyst/Admin roles, firing notifications/tools/list_changed.
server.disable(names={"approve_claim"}, components={"tool"})

print("="*50)
print("HARBORSTONE INSURANCE MCP SERVER")
print("="*50)
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


