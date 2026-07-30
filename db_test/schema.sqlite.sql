-- db_test/schema.sqlite.sql
-- Converted from SQL Server to SQLite
-- Harborstone Insurance Database

-- Disable foreign keys temporarily for creation
PRAGMA foreign_keys = OFF;

-- ============================================================================
-- 1. CUSTOMERS
-- ============================================================================
CREATE TABLE Customers(
    customer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_code VARCHAR(20) NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    national_id VARCHAR(20) NOT NULL UNIQUE,
    date_of_birth DATE,
    phone VARCHAR(20),
    email VARCHAR(100) UNIQUE,
    address TEXT,
    city TEXT,
    country TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'Active',
    CHECK(status IN ('Active','Inactive'))
);

-- ============================================================================
-- 2. EMPLOYEES
-- ============================================================================
CREATE TABLE Employees(
    employee_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_code VARCHAR(20) NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    role_name VARCHAR(50) NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(20),
    department TEXT,
    hire_date DATE,
    is_active INTEGER NOT NULL DEFAULT 1,
    CHECK(role_name IN
        ('Admin','Claims Officer','Underwriter','Marine Surveyor',
         'Finance','Risk Analyst','Customer Service',
         'Compliance','Operations','IT'))
);

-- ============================================================================
-- 3. VESSELS
-- ============================================================================
CREATE TABLE Vessels(
    vessel_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    vessel_name TEXT NOT NULL,
    registration_number VARCHAR(50) UNIQUE,
    imo_number VARCHAR(30),
    vessel_type VARCHAR(50),
    manufacturer TEXT,
    model TEXT,
    year_built INTEGER NOT NULL,
    gross_tonnage DECIMAL(10,2),
    insured_value DECIMAL(18,2) NOT NULL,
    current_location TEXT,
    CHECK(year_built >= 1950),
    CHECK(insured_value >= 0),
    FOREIGN KEY(customer_id) REFERENCES Customers(customer_id)
);

-- ============================================================================
-- 4. COVERAGE TYPES
-- ============================================================================
CREATE TABLE CoverageTypes(
    coverage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    coverage_name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

-- ============================================================================
-- 5. INSURANCE POLICIES
-- ============================================================================
CREATE TABLE InsurancePolicies(
    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    vessel_id INTEGER NOT NULL,
    policy_number VARCHAR(50) NOT NULL UNIQUE,
    policy_type VARCHAR(50),
    coverage_amount DECIMAL(18,2) NOT NULL,
    deductible DECIMAL(18,2) NOT NULL DEFAULT 0,
    premium DECIMAL(18,2) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'Active',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(coverage_amount > 0),
    CHECK(deductible >= 0),
    CHECK(premium >= 0),
    CHECK(end_date > start_date),
    CHECK(status IN ('Active','Expired','Cancelled')),
    FOREIGN KEY(customer_id) REFERENCES Customers(customer_id),
    FOREIGN KEY(vessel_id) REFERENCES Vessels(vessel_id)
);

-- ============================================================================
-- 6. POLICY COVERAGE
-- ============================================================================
CREATE TABLE PolicyCoverage(
    policy_coverage_id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id INTEGER NOT NULL,
    coverage_id INTEGER NOT NULL,
    coverage_limit DECIMAL(18,2) NOT NULL,
    CHECK(coverage_limit >= 0),
    UNIQUE(policy_id, coverage_id),
    FOREIGN KEY(policy_id) REFERENCES InsurancePolicies(policy_id),
    FOREIGN KEY(coverage_id) REFERENCES CoverageTypes(coverage_id)
);

-- ============================================================================
-- 7. CLAIMS
-- ============================================================================
CREATE TABLE Claims(
    claim_id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_id INTEGER NOT NULL,
    assigned_employee_id INTEGER,
    claim_number VARCHAR(50) NOT NULL UNIQUE,
    incident_date DATE NOT NULL,
    claim_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    claim_amount DECIMAL(18,2) NOT NULL,
    estimated_loss DECIMAL(18,2),
    damage_type VARCHAR(100),
    description TEXT,
    priority VARCHAR(20) NOT NULL DEFAULT 'Medium',
    risk_level VARCHAR(20) NOT NULL DEFAULT 'Low',
    status VARCHAR(30) NOT NULL DEFAULT 'Pending',
    CHECK(claim_amount >= 0),
    CHECK(estimated_loss >= 0),
    CHECK(claim_date >= incident_date),
    CHECK(priority IN ('Low','Medium','High')),
    CHECK(risk_level IN ('Low','Medium','High')),
    CHECK(status IN ('Pending','Under Review','Approved','Rejected','Paid')),
    FOREIGN KEY(policy_id) REFERENCES InsurancePolicies(policy_id),
    FOREIGN KEY(assigned_employee_id) REFERENCES Employees(employee_id)
);

-- ============================================================================
-- 8. FRAUD CHECKS
-- ============================================================================
CREATE TABLE FraudChecks(
    fraud_check_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL,
    fraud_score DECIMAL(5,2),
    ai_recommendation TEXT,
    checked_by INTEGER,
    checked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    fraud_status VARCHAR(30),
    CHECK(fraud_score BETWEEN 0 AND 100),
    CHECK(fraud_status IN ('Clear','Suspicious','Fraud')),
    FOREIGN KEY(claim_id) REFERENCES Claims(claim_id),
    FOREIGN KEY(checked_by) REFERENCES Employees(employee_id)
);

-- ============================================================================
-- 9. AUDIT LOGS
-- ============================================================================
CREATE TABLE AuditLogs(
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER,
    action TEXT NOT NULL,
    table_name TEXT,
    record_id INTEGER,
    action_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(50),
    FOREIGN KEY(employee_id) REFERENCES Employees(employee_id)
);

-- ============================================================================
-- 10. CLAIM WORKFLOW
-- ============================================================================
CREATE TABLE ClaimWorkflow(
    workflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL,
    employee_id INTEGER NOT NULL,
    workflow_stage VARCHAR(50) NOT NULL,
    action VARCHAR(50) NOT NULL,
    action_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    comments TEXT,
    FOREIGN KEY(claim_id) REFERENCES Claims(claim_id),
    FOREIGN KEY(employee_id) REFERENCES Employees(employee_id)
);

-- ============================================================================
-- 11. PAYMENTS
-- ============================================================================
CREATE TABLE Payments(
    payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id INTEGER NOT NULL,
    approved_by INTEGER,
    payment_amount DECIMAL(18,2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    payment_date DATETIME,
    payment_status VARCHAR(30) NOT NULL DEFAULT 'Pending',
    transaction_reference VARCHAR(100),
    CHECK(payment_amount >= 0),
    CHECK(payment_status IN ('Pending','Approved','Paid','Rejected')),
    CHECK(payment_method IN ('Bank Transfer','Credit Card','Cash','Cheque')),
    FOREIGN KEY(claim_id) REFERENCES Claims(claim_id),
    FOREIGN KEY(approved_by) REFERENCES Employees(employee_id)
);

-- Re-enable foreign keys
PRAGMA foreign_keys = ON;