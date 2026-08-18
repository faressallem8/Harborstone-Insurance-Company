USE HarborstoneInsurance;
GO

-- ============================================================
-- PLATFORM TABLES
-- These are new tables for the Final Project
-- They do not modify existing tables
-- ============================================================

-- 1. HITL Tasks (Human-in-the-Loop approvals)
CREATE TABLE PlatformHITLTasks (
    id INT IDENTITY(1,1) PRIMARY KEY,
    graph_name NVARCHAR(50) NOT NULL,
    run_id NVARCHAR(50) NOT NULL,
    node_name NVARCHAR(50) NOT NULL,
    state NVARCHAR(MAX) NOT NULL,
    status NVARCHAR(20) NOT NULL DEFAULT 'pending',
    assigned_to NVARCHAR(50),
    created_at DATETIME NOT NULL DEFAULT GETDATE(),
    resolved_at DATETIME,

    CONSTRAINT CK_HITL_Status CHECK (status IN ('pending', 'resolved', 'rejected'))
);
GO

-- 2. Failure Tickets
CREATE TABLE PlatformTickets (
    id INT IDENTITY(1,1) PRIMARY KEY,
    graph_name NVARCHAR(50) NOT NULL,
    run_id NVARCHAR(50) NOT NULL,
    node_name NVARCHAR(50),
    state NVARCHAR(MAX),
    error_message NVARCHAR(MAX) NOT NULL,
    status NVARCHAR(20) NOT NULL DEFAULT 'open',
    assigned_to NVARCHAR(50),
    created_at DATETIME NOT NULL DEFAULT GETDATE(),
    resolved_at DATETIME,

    CONSTRAINT CK_Ticket_Status CHECK (status IN ('open', 'investigating', 'resolved'))
);
GO

-- 3. Graph Checkpoints (for crash recovery)
CREATE TABLE PlatformGraphCheckpoints (
    id INT IDENTITY(1,1) PRIMARY KEY,
    graph_name NVARCHAR(50) NOT NULL,
    run_id NVARCHAR(50) NOT NULL,
    node_name NVARCHAR(50) NOT NULL,
    state NVARCHAR(MAX) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT GETDATE(),

    CONSTRAINT UQ_Checkpoint UNIQUE (graph_name, run_id, node_name)
);
GO

-- 4. Tool Registry (Admin toggles tools per agent)
CREATE TABLE PlatformToolRegistry (
    id INT IDENTITY(1,1) PRIMARY KEY,
    tool_name NVARCHAR(50) NOT NULL,
    agent_name NVARCHAR(50) NOT NULL,
    enabled BIT NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL DEFAULT GETDATE(),
    updated_at DATETIME,

    CONSTRAINT UQ_ToolAgent UNIQUE (tool_name, agent_name)
);
GO

-- 5. RAG Documents (Admin manages documents)
CREATE TABLE PlatformRAGDocuments (
    id INT IDENTITY(1,1) PRIMARY KEY,
    name NVARCHAR(100) NOT NULL,
    content NVARCHAR(MAX) NOT NULL,
    source NVARCHAR(50),
    active BIT NOT NULL DEFAULT 1,
    added_at DATETIME NOT NULL DEFAULT GETDATE(),
    updated_at DATETIME
);
GO

-- ============================================================
-- INITIAL DATA
-- ============================================================

INSERT INTO PlatformToolRegistry (tool_name, agent_name, enabled)
VALUES
    ('check_claim_status', 'Appeal Agent', 1),
    ('get_policy_details', 'Appeal Agent', 1),
    ('get_customer_info', 'Appeal Agent', 1),
    ('approve_claim', 'Appeal Agent', 1),

    ('check_claim_status', 'Renewal Agent', 1),
    ('get_policy_details', 'Renewal Agent', 1),
    ('get_customer_info', 'Renewal Agent', 1),
    ('assess_risk', 'Renewal Agent', 1),

    ('check_claim_status', 'Fraud Agent', 1),
    ('get_policy_details', 'Fraud Agent', 1),
    ('get_customer_info', 'Fraud Agent', 1),
    ('approve_claim', 'Fraud Agent', 1);
GO

INSERT INTO PlatformRAGDocuments (name, content, source, active)
VALUES (
    'Harborstone Underwriting Manual',
    'HARBORSTONE INSURANCE – MARINE UNDERWRITING & CLAIMS MANUAL
Version 4.2 (Effective: Jan 2025)

SECTION 1: GENERAL UNDERWRITING GUIDELINES
1.1 Eligibility: All vessels must be registered and seaworthy. Vessels over 25 years old require a special survey.
1.2 Coverage Limits: Standard policies cover up to $250,000. Excess coverage requires board approval.
1.3 Deductibles:
  - Vessels < 10 years old: $500 deductible.
  - Vessels 10–20 years old: $1,000 deductible.
  - Vessels > 20 years old: $2,500 deductible.
1.4 Premium Basis: 1.5% of insured value for pleasure craft; 2.5% for commercial fishing vessels.

SECTION 2: RISK ASSESSMENT PROTOCOLS
2.1 Cardiac-Risk Vessels: Any vessel with a history of engine failure or electrical fires is classified as "Cardiac-Risk".
  - Pre-underwriting screening: Mandatory engine compression test and electrical system audit.
  - Premium adjustment: Add 0.75% to standard premium.
2.2 Age Factors:
  - Vessels 15-20 years: +0.5% premium surcharge.
  - Vessels > 20 years: +1.0% surcharge + mandatory dry-dock inspection.

SECTION 3: CLAIMS PROCESSING STANDARDS
3.1 Filing Window: Claims must be filed within 30 days of the incident.
3.2 Approval Thresholds:
  - Claims under $10,000: Auto-approval by system.
  - Claims $10,001 – $50,000: Requires Underwriter approval.
  - Claims over $50,000: Requires Admin approval + loss adjuster report.',
    'policy_manual',
    1
);
GO