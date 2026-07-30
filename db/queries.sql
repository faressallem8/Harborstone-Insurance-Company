USE HarborstoneInsurance;
GO

/*
  TEST Record Count
*/

SELECT 'Customers' AS TableName, COUNT(*) AS TotalRecords FROM Customers
UNION ALL
SELECT 'Employees', COUNT(*) FROM Employees
UNION ALL
SELECT 'Vessels', COUNT(*) FROM Vessels
UNION ALL
SELECT 'CoverageTypes', COUNT(*) FROM CoverageTypes
UNION ALL
SELECT 'InsurancePolicies', COUNT(*) FROM InsurancePolicies
UNION ALL
SELECT 'PolicyCoverage', COUNT(*) FROM PolicyCoverage
UNION ALL
SELECT 'Claims', COUNT(*) FROM Claims
UNION ALL
SELECT 'FraudChecks', COUNT(*) FROM FraudChecks
UNION ALL
SELECT 'AuditLogs', COUNT(*) FROM AuditLogs
UNION ALL
SELECT 'ClaimWorkflow', COUNT(*) FROM ClaimWorkflow
UNION ALL
SELECT 'Payments', COUNT(*) FROM Payments;
GO

/*
  TEST Customer -> Vessel
*/

SELECT
    c.customer_code,
    c.full_name,
    v.vessel_name,
    v.vessel_type
FROM Customers c
JOIN Vessels v
ON c.customer_id = v.customer_id;
GO

/*
  TEST Policy Details
*/

SELECT
    p.policy_number,
    c.full_name,
    v.vessel_name,
    p.coverage_amount,
    p.status
FROM InsurancePolicies p
JOIN Customers c
ON p.customer_id = c.customer_id
JOIN Vessels v
ON p.vessel_id = v.vessel_id;
GO

/*
  TEST Policy Coverage
*/

SELECT
    p.policy_number,
    ct.coverage_name,
    pc.coverage_limit
FROM PolicyCoverage pc
JOIN InsurancePolicies p
ON pc.policy_id = p.policy_id
JOIN CoverageTypes ct
ON pc.coverage_id = ct.coverage_id;
GO

/*
  TEST Claims
*/

SELECT
    cl.claim_number,
    c.full_name,
    e.full_name AS AssignedEmployee,
    cl.claim_amount,
    cl.status
FROM Claims cl
JOIN InsurancePolicies p
ON cl.policy_id = p.policy_id
JOIN Customers c
ON p.customer_id = c.customer_id
LEFT JOIN Employees e
ON cl.assigned_employee_id = e.employee_id;
GO

/*
  TEST Fraud Checks
*/

SELECT
    cl.claim_number,
    f.fraud_score,
    f.fraud_status,
    e.full_name AS CheckedBy
FROM FraudChecks f
JOIN Claims cl
ON f.claim_id = cl.claim_id
LEFT JOIN Employees e
ON f.checked_by = e.employee_id;
GO

/*
  TEST Claim Workflow
*/

SELECT
    cl.claim_number,
    w.workflow_stage,
    w.action,
    e.full_name
FROM ClaimWorkflow w
JOIN Claims cl
ON w.claim_id = cl.claim_id
JOIN Employees e
ON w.employee_id = e.employee_id
ORDER BY cl.claim_number;
GO

/*
  TEST Payments
*/

SELECT
    cl.claim_number,
    p.payment_amount,
    p.payment_method,
    p.payment_status,
    e.full_name AS ApprovedBy
FROM Payments p
JOIN Claims cl
ON p.claim_id = cl.claim_id
LEFT JOIN Employees e
ON p.approved_by = e.employee_id;
GO

/*
  TEST Policies Per Customer
*/

SELECT
    c.full_name,
    COUNT(p.policy_id) AS TotalPolicies
FROM Customers c
LEFT JOIN InsurancePolicies p
ON c.customer_id = p.customer_id
GROUP BY c.full_name
ORDER BY TotalPolicies DESC;
GO

/*
  TEST Claims Per Policy
*/

SELECT
    p.policy_number,
    COUNT(c.claim_id) AS TotalClaims
FROM InsurancePolicies p
LEFT JOIN Claims c
ON p.policy_id = c.policy_id
GROUP BY p.policy_number
ORDER BY TotalClaims DESC;
GO

/*
  TEST Total Paid Amount
*/

SELECT
    SUM(payment_amount) AS TotalPaidAmount
FROM Payments
WHERE payment_status = 'Paid';
GO

/*
  TEST  Vessel Count Per Customer
*/

SELECT
    c.full_name,
    COUNT(v.vessel_id) AS TotalVessels
FROM Customers c
LEFT JOIN Vessels v
ON c.customer_id = v.customer_id
GROUP BY c.full_name
ORDER BY TotalVessels DESC;
GO