USE HarborstoneInsurance;
GO

CREATE TABLE Customers(
    customer_id INT IDENTITY(1,1) PRIMARY KEY,
    customer_code VARCHAR(20) NOT NULL UNIQUE,
    full_name NVARCHAR(100) NOT NULL,
    national_id VARCHAR(20) NOT NULL UNIQUE,
    date_of_birth DATE,
    phone VARCHAR(20),
    email VARCHAR(100) UNIQUE,
    address NVARCHAR(255),
    city NVARCHAR(100),
    country NVARCHAR(100),
    created_at DATETIME NOT NULL DEFAULT GETDATE(),
    status VARCHAR(20) NOT NULL DEFAULT 'Active',
    CONSTRAINT CK_Customer_Status 
        CHECK(status IN ('Active','Inactive'))
);
GO

CREATE TABLE Employees(
    employee_id INT IDENTITY(1,1) PRIMARY KEY,
    employee_code VARCHAR(20) NOT NULL UNIQUE,
    full_name NVARCHAR(100) NOT NULL,
    role_name VARCHAR(50) NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(20),
    department NVARCHAR(100),
    hire_date DATE,
    is_active BIT NOT NULL DEFAULT 1,
    CONSTRAINT CK_Employee_Role 
        CHECK(role_name IN 
        ('Admin','Claims Officer','Underwriter','Marine Surveyor',
         'Finance','Risk Analyst','Customer Service',
         'Compliance','Operations','IT'))
);
GO

CREATE TABLE Vessels(
    vessel_id INT IDENTITY(1,1) PRIMARY KEY,
    customer_id INT NOT NULL,
    vessel_name NVARCHAR(100) NOT NULL,
    registration_number VARCHAR(50) UNIQUE,
    imo_number VARCHAR(30),
    vessel_type VARCHAR(50),
    manufacturer NVARCHAR(100),
    model NVARCHAR(100),
    year_built INT NOT NULL,
    gross_tonnage DECIMAL(10,2),
    insured_value DECIMAL(18,2) NOT NULL,
    current_location NVARCHAR(150),
    CONSTRAINT CK_Vessel_Year 
        CHECK (year_built BETWEEN 1950 AND YEAR(GETDATE())),
    CONSTRAINT CK_Vessel_Value 
        CHECK(insured_value >= 0),
    CONSTRAINT FK_Vessel_Customer 
        FOREIGN KEY(customer_id) 
        REFERENCES Customers(customer_id)
);
GO

CREATE TABLE CoverageTypes(
    coverage_id INT IDENTITY(1,1) PRIMARY KEY,
    coverage_name VARCHAR(100) NOT NULL UNIQUE,
    description NVARCHAR(MAX)
);
GO

CREATE TABLE InsurancePolicies(
    policy_id INT IDENTITY(1,1) PRIMARY KEY,
    customer_id INT NOT NULL,
    vessel_id INT NOT NULL,
    policy_number VARCHAR(50) NOT NULL UNIQUE,
    policy_type VARCHAR(50),
    coverage_amount DECIMAL(18,2) NOT NULL,
    deductible DECIMAL(18,2) NOT NULL DEFAULT 0,
    premium DECIMAL(18,2) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'Active',
    created_at DATETIME NOT NULL DEFAULT GETDATE(),

    CONSTRAINT CK_Policy_Coverage CHECK(coverage_amount > 0),
    CONSTRAINT CK_Policy_Deductible CHECK(deductible >= 0),
    CONSTRAINT CK_Policy_Premium CHECK(premium >= 0),
    CONSTRAINT CK_Policy_Dates CHECK(end_date > start_date),
    CONSTRAINT CK_Policy_Status CHECK(status IN ('Active','Expired','Cancelled')),

    CONSTRAINT FK_Policy_Customer 
        FOREIGN KEY(customer_id) 
        REFERENCES Customers(customer_id),

    CONSTRAINT FK_Policy_Vessel 
        FOREIGN KEY(vessel_id) 
        REFERENCES Vessels(vessel_id)
);
GO

CREATE TABLE PolicyCoverage(
    policy_coverage_id INT IDENTITY(1,1) PRIMARY KEY,
    policy_id INT NOT NULL,
    coverage_id INT NOT NULL,
    coverage_limit DECIMAL(18,2) NOT NULL,

    CONSTRAINT CK_Coverage_Limit 
        CHECK(coverage_limit >= 0),

    CONSTRAINT UQ_PolicyCoverage 
        UNIQUE(policy_id,coverage_id),

    CONSTRAINT FK_PC_Policy 
        FOREIGN KEY(policy_id) 
        REFERENCES InsurancePolicies(policy_id),

    CONSTRAINT FK_PC_Coverage 
        FOREIGN KEY(coverage_id) 
        REFERENCES CoverageTypes(coverage_id)
);
GO

CREATE TABLE Claims(
    claim_id INT IDENTITY(1,1) PRIMARY KEY,
    policy_id INT NOT NULL,
    assigned_employee_id INT,
    claim_number VARCHAR(50) NOT NULL UNIQUE,
    incident_date DATE NOT NULL,
    claim_date DATETIME NOT NULL DEFAULT GETDATE(),
    claim_amount DECIMAL(18,2) NOT NULL,
    estimated_loss DECIMAL(18,2),
    damage_type VARCHAR(100),
    description NVARCHAR(MAX),
    priority VARCHAR(20) NOT NULL DEFAULT 'Medium',
    risk_level VARCHAR(20) NOT NULL DEFAULT 'Low',
    status VARCHAR(30) NOT NULL DEFAULT 'Pending',

    CONSTRAINT CK_Claim_Amount 
        CHECK(claim_amount >= 0),

    CONSTRAINT CK_Estimated_Loss 
        CHECK(estimated_loss >= 0),

    CONSTRAINT CK_Claim_Dates 
        CHECK(claim_date >= incident_date),

    CONSTRAINT CK_Claim_Priority 
        CHECK(priority IN ('Low','Medium','High')),

    CONSTRAINT CK_Risk_Level 
        CHECK(risk_level IN ('Low','Medium','High')),

    CONSTRAINT CK_Claim_Status 
        CHECK(status IN ('Pending','Under Review','Approved','Rejected','Paid')),

    CONSTRAINT FK_Claim_Policy 
        FOREIGN KEY(policy_id) 
        REFERENCES InsurancePolicies(policy_id),

    CONSTRAINT FK_Claim_Employee 
        FOREIGN KEY(assigned_employee_id) 
        REFERENCES Employees(employee_id)
);
GO

CREATE TABLE FraudChecks(
    fraud_check_id INT IDENTITY(1,1) PRIMARY KEY,
    claim_id INT NOT NULL,
    fraud_score DECIMAL(5,2),
    ai_recommendation NVARCHAR(255),
    checked_by INT,
    checked_at DATETIME DEFAULT GETDATE(),
    fraud_status VARCHAR(30),

    CONSTRAINT CK_Fraud_Score 
        CHECK(fraud_score BETWEEN 0 AND 100),

    CONSTRAINT CK_Fraud_Status 
        CHECK(fraud_status IN ('Clear','Suspicious','Fraud')),

    CONSTRAINT FK_Fraud_Claim 
        FOREIGN KEY(claim_id) 
        REFERENCES Claims(claim_id),

    CONSTRAINT FK_Fraud_Employee 
        FOREIGN KEY(checked_by) 
        REFERENCES Employees(employee_id)
);
GO

CREATE TABLE AuditLogs(
    log_id INT IDENTITY(1,1) PRIMARY KEY,
    employee_id INT,
    action NVARCHAR(100) NOT NULL,
    table_name NVARCHAR(100),
    record_id INT,
    action_time DATETIME NOT NULL DEFAULT GETDATE(),
    ip_address VARCHAR(50),

    CONSTRAINT FK_Audit_Employee 
        FOREIGN KEY(employee_id) 
        REFERENCES Employees(employee_id)
);
GO

CREATE TABLE ClaimWorkflow(
    workflow_id INT IDENTITY(1,1) PRIMARY KEY,
    claim_id INT NOT NULL,
    employee_id INT NOT NULL,
    workflow_stage VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    action_date DATETIME NOT NULL DEFAULT GETDATE(),
    comments NVARCHAR(MAX),

    CONSTRAINT FK_Workflow_Claim 
        FOREIGN KEY(claim_id) 
        REFERENCES Claims(claim_id),

    CONSTRAINT FK_Workflow_Employee 
        FOREIGN KEY(employee_id) 
        REFERENCES Employees(employee_id)
);
GO

CREATE TABLE Payments(
    payment_id INT IDENTITY(1,1) PRIMARY KEY,
    claim_id INT NOT NULL,
    approved_by INT,
    payment_amount DECIMAL(18,2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    payment_date DATETIME,
    payment_status VARCHAR(30) NOT NULL DEFAULT 'Pending',
    transaction_reference VARCHAR(100),

    CONSTRAINT CK_Payment_Amount 
        CHECK(payment_amount >= 0),

    CONSTRAINT CK_Payment_Status 
        CHECK(payment_status IN ('Pending','Approved','Paid','Rejected')),

    CONSTRAINT CK_Payment_Method 
        CHECK(payment_method IN ('Bank Transfer','Credit Card','Cash','Cheque')),

    CONSTRAINT FK_Payment_Claim 
        FOREIGN KEY(claim_id) 
        REFERENCES Claims(claim_id),

    CONSTRAINT FK_Payment_Employee 
        FOREIGN KEY(approved_by) 
        REFERENCES Employees(employee_id)
);
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.tables
    WHERE name = 'PlatformHITLTasks'
)
BEGIN
    CREATE TABLE PlatformHITLTasks (
        id INT IDENTITY(1,1) PRIMARY KEY,

        graph_name NVARCHAR(50) NOT NULL,
        run_id NVARCHAR(50) NOT NULL,
        node_name NVARCHAR(50) NOT NULL,

        -- Full graph state stored as JSON
        state NVARCHAR(MAX) NOT NULL,

        -- Admin decision stored as JSON
        decision NVARCHAR(MAX),

        status NVARCHAR(20) NOT NULL DEFAULT 'pending',

        assigned_to NVARCHAR(50),

        -- HITL priority
        priority NVARCHAR(20) NOT NULL DEFAULT 'medium',

        created_at DATETIME NOT NULL DEFAULT GETDATE(),
        resolved_at DATETIME,

        -- Admin resolution notes
        resolution_notes NVARCHAR(MAX),

        CONSTRAINT CK_HITL_Status
            CHECK (status IN ('pending', 'resolved', 'rejected')),

        CONSTRAINT CK_HITL_Priority
            CHECK (priority IN ('low', 'medium', 'high', 'urgent'))
    );
END
GO


-- ============================================================
-- 2. Failure Tickets
-- ============================================================

IF NOT EXISTS (
    SELECT 1
    FROM sys.tables
    WHERE name = 'PlatformTickets'
)
BEGIN
    CREATE TABLE PlatformTickets (
        id INT IDENTITY(1,1) PRIMARY KEY,

        graph_name NVARCHAR(50) NOT NULL,
        run_id NVARCHAR(50) NOT NULL,
        node_name NVARCHAR(50),

        -- Graph state at failure
        state NVARCHAR(MAX),

        error_message NVARCHAR(MAX) NOT NULL,
        error_type NVARCHAR(100),

        status NVARCHAR(20) NOT NULL DEFAULT 'open',

        assigned_to NVARCHAR(50),

        created_at DATETIME NOT NULL DEFAULT GETDATE(),
        resolved_at DATETIME,

        -- Admin resolution notes
        resolution_notes NVARCHAR(MAX),

        -- Ticket severity
        severity NVARCHAR(20) NOT NULL DEFAULT 'medium',

        CONSTRAINT CK_Ticket_Status
            CHECK (status IN ('open', 'investigating', 'resolved')),

        CONSTRAINT CK_Ticket_Severity
            CHECK (severity IN ('low', 'medium', 'high', 'critical'))
    );
END
GO


-- ============================================================
-- 3. Graph Checkpoints
-- Used for crash recovery
-- ============================================================

IF NOT EXISTS (
    SELECT 1
    FROM sys.tables
    WHERE name = 'PlatformGraphCheckpoints'
)
BEGIN
    CREATE TABLE PlatformGraphCheckpoints (
        id INT IDENTITY(1,1) PRIMARY KEY,

        graph_name NVARCHAR(50) NOT NULL,
        run_id NVARCHAR(50) NOT NULL,
        node_name NVARCHAR(50) NOT NULL,

        -- Full graph state stored as JSON
        state NVARCHAR(MAX) NOT NULL,

        created_at DATETIME NOT NULL DEFAULT GETDATE(),

        CONSTRAINT UQ_Checkpoint
            UNIQUE (graph_name, run_id, node_name)
    );
END
GO


-- ============================================================
-- 4. Tool Registry
-- Admin toggles tools per agent
-- ============================================================

IF NOT EXISTS (
    SELECT 1
    FROM sys.tables
    WHERE name = 'PlatformToolRegistry'
)
BEGIN
    CREATE TABLE PlatformToolRegistry (
        id INT IDENTITY(1,1) PRIMARY KEY,

        tool_name NVARCHAR(50) NOT NULL,
        agent_name NVARCHAR(50) NOT NULL,

        enabled BIT NOT NULL DEFAULT 1,

        created_at DATETIME NOT NULL DEFAULT GETDATE(),
        updated_at DATETIME,

        CONSTRAINT UQ_ToolAgent
            UNIQUE (tool_name, agent_name)
    );
END
GO


-- ============================================================
-- 5. RAG Documents
-- Admin-managed RAG documents
-- ============================================================

IF NOT EXISTS (
    SELECT 1
    FROM sys.tables
    WHERE name = 'PlatformRAGDocuments'
)
BEGIN
    CREATE TABLE PlatformRAGDocuments (
        id INT IDENTITY(1,1) PRIMARY KEY,

        name NVARCHAR(100) NOT NULL,
        content NVARCHAR(MAX) NOT NULL,

        source NVARCHAR(50),

        active BIT NOT NULL DEFAULT 1,

        added_at DATETIME NOT NULL DEFAULT GETDATE(),
        updated_at DATETIME
    );
END
GO


-- ============================================================
-- INITIAL TOOL REGISTRY DATA
-- ============================================================

IF NOT EXISTS (
    SELECT 1
    FROM PlatformToolRegistry
    WHERE tool_name = 'check_claim_status'
      AND agent_name = 'Appeal Agent'
)
BEGIN
    INSERT INTO PlatformToolRegistry
        (tool_name, agent_name, enabled)
    VALUES
        ('check_claim_status', 'Appeal Agent', 1),
        ('get_policy_details', 'Appeal Agent', 1),
        ('get_customer_info', 'Appeal Agent', 1),
        ('approve_claim', 'Appeal Agent', 1);
END
GO


IF NOT EXISTS (
    SELECT 1
    FROM PlatformToolRegistry
    WHERE tool_name = 'check_claim_status'
      AND agent_name = 'Renewal Agent'
)
BEGIN
    INSERT INTO PlatformToolRegistry
        (tool_name, agent_name, enabled)
    VALUES
        ('check_claim_status', 'Renewal Agent', 1),
        ('get_policy_details', 'Renewal Agent', 1),
        ('get_customer_info', 'Renewal Agent', 1),
        ('assess_risk', 'Renewal Agent', 1);
END
GO


IF NOT EXISTS (
    SELECT 1
    FROM PlatformToolRegistry
    WHERE tool_name = 'check_claim_status'
      AND agent_name = 'Fraud Agent'
)
BEGIN
    INSERT INTO PlatformToolRegistry
        (tool_name, agent_name, enabled)
    VALUES
        ('check_claim_status', 'Fraud Agent', 1),
        ('get_policy_details', 'Fraud Agent', 1),
        ('get_customer_info', 'Fraud Agent', 1),
        ('approve_claim', 'Fraud Agent', 1);
END
GO


-- ============================================================
-- INITIAL RAG DOCUMENT
-- ============================================================

IF NOT EXISTS (
    SELECT 1
    FROM PlatformRAGDocuments
    WHERE name = 'Harborstone Underwriting Manual'
)
BEGIN
    INSERT INTO PlatformRAGDocuments
        (name, content, source, active)
    VALUES
    (
        'Harborstone Underwriting Manual',

        'HARBORSTONE INSURANCE – MARINE UNDERWRITING & CLAIMS MANUAL
Version 4.2 (Effective: Jan 2025)

SECTION 1: GENERAL UNDERWRITING GUIDELINES

1.1 Eligibility:
All vessels must be registered and seaworthy.
Vessels over 25 years old require a special survey.

1.2 Coverage Limits:
Standard policies cover up to $250,000.
Excess coverage requires board approval.

1.3 Deductibles:
- Vessels < 10 years old: $500 deductible.
- Vessels 10–20 years old: $1,000 deductible.
- Vessels > 20 years old: $2,500 deductible.

1.4 Premium Basis:
- 1.5% of insured value for pleasure craft.
- 2.5% for commercial fishing vessels.

SECTION 2: RISK ASSESSMENT PROTOCOLS

2.1 Cardiac-Risk Vessels:
Any vessel with a history of engine failure or electrical fires is classified as "Cardiac-Risk".

- Pre-underwriting screening:
  Mandatory engine compression test and electrical system audit.

- Premium adjustment:
  Add 0.75% to standard premium.

2.2 Age Factors:
- Vessels 15-20 years: +0.5% premium surcharge.
- Vessels > 20 years: +1.0% surcharge + mandatory dry-dock inspection.

SECTION 3: CLAIMS PROCESSING STANDARDS

3.1 Filing Window:
Claims must be filed within 30 days of the incident.

3.2 Approval Thresholds:
- Claims under $10,000: Auto-approval by system.
- Claims $10,001 – $50,000: Requires Underwriter approval.
- Claims over $50,000: Requires Admin approval + loss adjuster report.',

        'policy_manual',
        1
    );
END
GO


-- ============================================================
-- VERIFICATION
-- ============================================================

SELECT
    TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME IN (
    'PlatformHITLTasks',
    'PlatformTickets',
    'PlatformGraphCheckpoints',
    'PlatformToolRegistry',
    'PlatformRAGDocuments'
)
ORDER BY TABLE_NAME;
GO


-- Check HITL columns
SELECT
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'PlatformHITLTasks'
ORDER BY ORDINAL_POSITION;
GO


-- Check Ticket columns
SELECT
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'PlatformTickets'
ORDER BY ORDINAL_POSITION;
GO



