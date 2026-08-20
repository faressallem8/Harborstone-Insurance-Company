USE HarborstoneInsurance;
GO

-- ============================================================
-- PLATFORM TABLES
-- These tables are used by the Harborstone Insurance Platform.
-- They do not modify existing business tables.
-- ============================================================


-- ============================================================
-- 1. HITL Tasks
-- Human-in-the-Loop approvals
-- ============================================================

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



