USE HarborstoneInsurance;
GO

INSERT INTO Customers
(customer_code, full_name, national_id, date_of_birth, phone, email, address, city, country, status)
VALUES
('CUST001','John Smith','900101000001','1990-01-01','+12025550101','john.smith@email.com','12 King St','New York','USA','Active'),
('CUST002','Emma Johnson','920315000002','1992-03-15','+442071111111','emma.j@email.com','8 Oxford Rd','London','UK','Active'),
('CUST003','Michael Brown','880720000003','1988-07-20','+491511111111','michael.b@email.com','22 River St','Hamburg','Germany','Active'),
('CUST004','Olivia Davis','950425000004','1995-04-25','+331401111111','olivia.d@email.com','15 Rue Paris','Paris','France','Active'),
('CUST005','William Wilson','870915000005','1987-09-15','+61281111111','william.w@email.com','10 George St','Sydney','Australia','Active'),
('CUST006','Sophia Moore','910530000006','1991-05-30','+971501111111','sophia.m@email.com','Palm Street','Dubai','UAE','Active'),
('CUST007','James Taylor','930812000007','1993-08-12','+6591111111','james.t@email.com','Marina Bay','Singapore','Singapore','Inactive'),
('CUST008','Charlotte Anderson','890205000008','1989-02-05','+81311111111','charlotte.a@email.com','Shibuya','Tokyo','Japan','Active'),
('CUST009','Daniel Thomas','940618000009','1994-06-18','+390611111111','daniel.t@email.com','Via Roma','Rome','Italy','Active'),
('CUST010','Isabella Martin','960921000010','1996-09-21','+34611111111','isabella.m@email.com','Gran Via','Madrid','Spain','Active');

INSERT INTO Employees
(employee_code, full_name, role_name, username, email, phone, department, hire_date, is_active)
VALUES
('EMP001','Robert Miller','Admin','rmiller','robert@harborstone.com','+12025551001','Administration','2020-01-10',1),
('EMP002','Sarah Wilson','Claims Officer','swilson','sarah@harborstone.com','+12025551002','Claims','2021-03-15',1),
('EMP003','David Moore','Underwriter','dmoore','david@harborstone.com','+12025551003','Underwriting','2019-06-01',1),
('EMP004','Emily Taylor','Marine Surveyor','etaylor','emily@harborstone.com','+12025551004','Survey','2022-02-18',1),
('EMP005','Christopher White','Finance','cwhite','chris@harborstone.com','+12025551005','Finance','2020-08-12',1),
('EMP006','Jessica Harris','Risk Analyst','jharris','jessica@harborstone.com','+12025551006','Risk','2021-11-20',1),
('EMP007','Andrew Clark','Customer Service','aclark','andrew@harborstone.com','+12025551007','Support','2023-01-09',1),
('EMP008','Laura Lewis','Compliance','llewis','laura@harborstone.com','+12025551008','Compliance','2018-04-25',1),
('EMP009','Matthew Walker','Operations','mwalker','matthew@harborstone.com','+12025551009','Operations','2019-09-30',1),
('EMP010','Sophia Hall','IT','shall','sophia@harborstone.com','+12025551010','IT','2022-07-14',1);

INSERT INTO Vessels
(customer_id,vessel_name,registration_number,imo_number,vessel_type,manufacturer,model,year_built,gross_tonnage,insured_value,current_location)
VALUES
(1,'Ocean Spirit','REG001','IMO100001','Cargo','Hyundai','HDC-500',2015,35000,5000000,'New York'),
(1,'Ocean King','REG002','IMO100002','Cargo','Hyundai','HDC-800',2021,38000,6100000,'Miami'),
(2,'Sea Explorer','REG003','IMO100003','Tanker','Samsung','STM-800',2018,42000,7200000,'London'),
(2,'Sea Falcon','REG004','IMO100004','Fishing','VARD','VF-500',2020,17000,2800000,'Liverpool'),
(3,'Atlantic Queen','REG005','IMO100005','Container','Mitsubishi','MC-900',2016,39000,6500000,'Hamburg'),
(4,'Blue Horizon','REG006','IMO100006','Passenger','Fincantieri','FH-700',2020,28000,8100000,'Marseille'),
(5,'Pacific Star','REG007','IMO100007','Cargo','Daewoo','DW-600',2014,33000,4700000,'Sydney'),
(5,'Blue Whale','REG008','IMO100008','Tanker','Samsung','ST-950',2019,45000,8900000,'Melbourne'),
(6,'Northern Wind','REG009','IMO100009','Fishing','VARD','VF-300',2019,12000,2400000,'Dubai'),
(7,'Golden Wave','REG010','IMO100010','Research','Damen','DR-400',2021,15000,3900000,'Singapore'),
(7,'Atlantic Sky','REG011','IMO100011','Research','Damen','DR-700',2022,19000,4100000,'Singapore'),
(8,'Silver Ocean','REG012','IMO100012','Passenger','Meyer Werft','MW-750',2017,30000,7800000,'Tokyo'),
(9,'Royal Neptune','REG013','IMO100013','Cargo','Hyundai','HDC-900',2013,36000,5600000,'Rome'),
(10,'Liberty Sea','REG014','IMO100014','Container','Samsung','STM-950',2022,44000,9300000,'Barcelona'),
(10,'Royal Ocean','REG015','IMO100015','Passenger','Meyer Werft','MW-900',2023,32000,9700000,'Valencia');

INSERT INTO CoverageTypes
(coverage_name,description)
VALUES
('Hull Damage','Physical damage to vessel hull'),
('Cargo Protection','Cargo loss or damage'),
('Third Party Liability','Third-party liability'),
('Collision Damage','Collision with another vessel'),
('Fire and Explosion','Fire and explosion damage'),
('Piracy Protection','Piracy-related incidents'),
('Environmental Liability','Pollution and environmental damage'),
('Crew Personal Accident','Crew injury coverage'),
('Machinery Breakdown','Engine and machinery failure'),
('War Risk','War and terrorism risks');

INSERT INTO InsurancePolicies
(customer_id,vessel_id,policy_number,policy_type,coverage_amount,deductible,premium,start_date,end_date,status)
VALUES
(1,1,'POL001','Marine Cargo',5000000,50000,120000,'2025-01-01','2025-12-31','Active'),
(1,2,'POL002','Hull Insurance',6100000,60000,145000,'2025-02-01','2026-01-31','Active'),
(2,3,'POL003','Oil Tanker',7200000,70000,165000,'2025-03-01','2026-02-28','Active'),
(2,4,'POL004','Fishing Vessel',2800000,30000,85000,'2025-04-01','2026-03-31','Active'),
(3,5,'POL005','Container Ship',6500000,65000,150000,'2025-05-01','2026-04-30','Active'),
(4,6,'POL006','Passenger Vessel',8100000,80000,190000,'2025-06-01','2026-05-31','Active'),
(5,7,'POL007','Marine Cargo',4700000,45000,110000,'2025-07-01','2026-06-30','Active'),
(5,8,'POL008','Oil Tanker',8900000,90000,210000,'2025-08-01','2026-07-31','Active'),
(6,9,'POL009','Fishing Vessel',2400000,25000,70000,'2025-09-01','2026-08-31','Active'),
(7,10,'POL010','Research Vessel',3900000,40000,98000,'2025-10-01','2026-09-30','Active'),
(7,11,'POL011','Research Vessel',4100000,45000,105000,'2025-11-01','2026-10-31','Active'),
(8,12,'POL012','Passenger Vessel',7800000,75000,180000,'2025-12-01','2026-11-30','Active'),
(9,13,'POL013','Marine Cargo',5600000,55000,130000,'2026-01-01','2026-12-31','Active'),
(10,14,'POL014','Container Ship',9300000,90000,220000,'2026-02-01','2027-01-31','Active'),
(10,15,'POL015','Passenger Vessel',9700000,95000,235000,'2026-03-01','2027-02-28','Active');

INSERT INTO PolicyCoverage (policy_id,coverage_id,coverage_limit)
VALUES
(1,1,3000000),(1,2,1500000),(1,5,500000),

(2,1,3500000),(2,4,1200000),

(3,1,4000000),(3,5,1800000),(3,7,1000000),

(4,8,1200000),(4,9,1000000),

(5,1,3000000),(5,2,2500000),(5,3,1000000),

(6,1,4500000),(6,8,2000000),

(7,2,2500000),(7,4,1500000),

(8,1,5000000),(8,5,2500000),(8,7,1000000),

(9,8,1200000),(9,9,1000000),

(10,3,1500000),(10,8,1500000),

(11,3,1800000),(11,10,1500000),

(12,1,4000000),(12,8,2500000),

(13,2,3000000),(13,4,1800000),

(14,1,5500000),(14,5,2500000),

(15,1,6000000),(15,8,2500000),(15,10,1200000);

INSERT INTO Claims
(policy_id,assigned_employee_id,claim_number,incident_date,claim_date,claim_amount,estimated_loss,damage_type,description,priority,risk_level,status)
VALUES
(1,2,'CLM001','2025-02-10','2025-02-11',120000,150000,'Hull Damage','Minor collision','Medium','Low','Approved'),
(1,2,'CLM002','2025-05-15','2025-05-16',90000,100000,'Cargo Damage','Cargo shifted','Low','Low','Paid'),

(2,3,'CLM003','2025-03-10','2025-03-11',200000,250000,'Fire','Engine fire','High','High','Pending'),

(3,4,'CLM004','2025-04-01','2025-04-03',350000,420000,'Collision','Sea collision','High','High','Approved'),
(3,4,'CLM005','2025-08-08','2025-08-09',180000,200000,'Machinery','Engine failure','Medium','Medium','Paid'),

(4,5,'CLM006','2025-06-01','2025-06-02',70000,90000,'Crew Injury','Crew accident','Low','Low','Approved'),

(5,6,'CLM007','2025-07-11','2025-07-12',150000,180000,'Cargo Damage','Water damage','Medium','Medium','Pending'),
(5,6,'CLM008','2025-09-20','2025-09-21',110000,120000,'Fire','Electrical fire','Medium','Medium','Approved'),

(6,7,'CLM009','2025-10-01','2025-10-02',500000,650000,'Collision','Dock accident','High','High','Paid'),

(7,8,'CLM010','2025-10-15','2025-10-16',80000,90000,'Hull Damage','Minor damage','Low','Low','Approved'),

(8,9,'CLM011','2025-11-10','2025-11-11',450000,500000,'Explosion','Tank explosion','High','High','Rejected'),

(9,10,'CLM012','2025-12-02','2025-12-03',60000,70000,'Machinery','Pump failure','Low','Low','Approved'),

(10,2,'CLM013','2026-01-15','2026-01-16',130000,150000,'Equipment','Research equipment','Medium','Low','Pending'),

(11,3,'CLM014','2026-02-01','2026-02-02',170000,200000,'Collision','Port collision','Medium','Medium','Approved'),

(12,4,'CLM015','2026-03-05','2026-03-06',300000,350000,'Fire','Kitchen fire','High','Medium','Paid'),

(13,5,'CLM016','2026-04-01','2026-04-02',95000,120000,'Cargo Damage','Container damage','Medium','Low','Approved'),

(14,6,'CLM017','2026-05-01','2026-05-02',410000,480000,'Collision','Heavy collision','High','High','Pending'),

(15,7,'CLM018','2026-06-01','2026-06-02',210000,250000,'Crew Injury','Passenger injury','Medium','Medium','Approved'),

(15,8,'CLM019','2026-07-01','2026-07-02',180000,210000,'Fire','Electrical issue','Medium','Medium','Paid'),

(14,9,'CLM020','2026-08-01','2026-08-02',270000,300000,'Hull Damage','Storm damage','High','High','Approved');

INSERT INTO FraudChecks
(claim_id,fraud_score,ai_recommendation,checked_by,fraud_status)
VALUES
(1,12,'Low fraud risk',6,'Clear'),
(2,18,'Approve claim',6,'Clear'),
(3,82,'Investigate further',6,'Suspicious'),
(4,15,'Clear',6,'Clear'),
(5,28,'Manual review',6,'Suspicious'),
(6,9,'Approve',6,'Clear'),
(7,35,'Review documents',6,'Suspicious'),
(8,14,'Approve',6,'Clear'),
(9,65,'Detailed inspection',6,'Suspicious'),
(10,5,'Clear',6,'Clear'),
(11,94,'Reject claim',6,'Fraud'),
(12,10,'Approve',6,'Clear'),
(13,22,'Clear',6,'Clear'),
(14,48,'Manual review',6,'Suspicious'),
(15,16,'Approve',6,'Clear'),
(16,13,'Approve',6,'Clear'),
(17,88,'Potential fraud',6,'Fraud'),
(18,24,'Manual review',6,'Suspicious'),
(19,11,'Clear',6,'Clear'),
(20,17,'Approve',6,'Clear');

INSERT INTO AuditLogs
(employee_id,action,table_name,record_id,ip_address)
VALUES
(1,'Created Customer','Customers',1,'192.168.1.10'),
(1,'Created Customer','Customers',2,'192.168.1.11'),
(1,'Created Customer','Customers',3,'192.168.1.12'),
(2,'Created Policy','InsurancePolicies',1,'192.168.1.13'),
(2,'Created Policy','InsurancePolicies',2,'192.168.1.14'),
(2,'Updated Policy','InsurancePolicies',3,'192.168.1.15'),
(3,'Created Claim','Claims',1,'192.168.1.16'),
(3,'Created Claim','Claims',2,'192.168.1.17'),
(3,'Updated Claim','Claims',3,'192.168.1.18'),
(4,'Approved Claim','Claims',4,'192.168.1.19'),
(4,'Rejected Claim','Claims',11,'192.168.1.20'),
(5,'Fraud Check','FraudChecks',1,'192.168.1.21'),
(5,'Fraud Check','FraudChecks',2,'192.168.1.22'),
(5,'Fraud Check','FraudChecks',3,'192.168.1.23'),
(6,'Payment Approved','Payments',1,'192.168.1.24'),
(6,'Payment Completed','Payments',2,'192.168.1.25'),
(7,'Updated Customer','Customers',5,'192.168.1.26'),
(7,'Updated Vessel','Vessels',7,'192.168.1.27'),
(8,'Created Coverage','CoverageTypes',4,'192.168.1.28'),
(8,'Updated Coverage','CoverageTypes',5,'192.168.1.29'),
(9,'Login','Employees',9,'192.168.1.30'),
(9,'Logout','Employees',9,'192.168.1.31'),
(10,'System Backup','AuditLogs',1,'192.168.1.32'),
(2,'Updated Payment','Payments',3,'192.168.1.33'),
(4,'Claim Assigned','Claims',6,'192.168.1.34'),
(5,'Fraud Review','FraudChecks',7,'192.168.1.35'),
(6,'Payment Pending','Payments',4,'192.168.1.36'),
(8,'Policy Renewed','InsurancePolicies',14,'192.168.1.37'),
(9,'Customer Login','Customers',8,'192.168.1.38'),
(10,'Database Maintenance','AuditLogs',30,'192.168.1.39');

INSERT INTO ClaimWorkflow
(claim_id,employee_id,workflow_stage,action,comments)
VALUES
(1,2,'Submitted','Submit Claim','Claim submitted'),
(1,3,'Review','Review Claim','Documents verified'),

(2,2,'Submitted','Submit Claim','Claim submitted'),
(2,3,'Review','Review Claim','Verified'),

(3,2,'Submitted','Submit Claim','Claim submitted'),
(3,6,'Review','Fraud Review','Checking for fraud'),

(4,2,'Submitted','Submit Claim','Claim submitted'),
(4,3,'Review','Inspection','Inspection completed'),

(5,2,'Submitted','Submit Claim','Claim submitted'),
(5,3,'Review','Review Claim','Documents verified'),

(6,2,'Submitted','Submit Claim','Claim submitted'),
(6,3,'Review','Inspection','Inspection completed'),

(7,2,'Submitted','Submit Claim','Claim submitted'),
(7,6,'Review','Review Claim','Additional review required'),

(8,2,'Submitted','Submit Claim','Claim submitted'),
(8,3,'Review','Inspection','Inspection completed'),

(9,2,'Submitted','Submit Claim','Claim submitted'),
(9,6,'Review','Fraud Review','Fraud analysis completed'),

(10,2,'Submitted','Submit Claim','Claim submitted'),
(10,3,'Review','Review Claim','Documents verified'),

(11,2,'Submitted','Submit Claim','Claim submitted'),
(11,6,'Review','Fraud Review','High fraud score'),

(12,2,'Submitted','Submit Claim','Claim submitted'),
(12,3,'Review','Inspection','Inspection completed'),

(13,2,'Submitted','Submit Claim','Claim submitted'),
(13,3,'Review','Review Claim','Waiting for approval'),

(14,2,'Submitted','Submit Claim','Claim submitted'),
(14,3,'Review','Inspection','Inspection completed'),

(15,2,'Submitted','Submit Claim','Claim submitted'),
(15,3,'Review','Review Claim','Ready for payment'),

(16,2,'Submitted','Submit Claim','Claim submitted'),
(17,2,'Submitted','Submit Claim','Claim submitted'),
(18,2,'Submitted','Submit Claim','Claim submitted'),
(19,2,'Submitted','Submit Claim','Claim submitted'),
(20,2,'Submitted','Submit Claim','Claim submitted');

INSERT INTO Payments
(claim_id,approved_by,payment_amount,payment_method,payment_date,payment_status,transaction_reference)
VALUES
(1,5,120000,'Bank Transfer','2025-02-20','Paid','TXN001'),
(2,5,90000,'Cash','2025-05-20','Paid','TXN002'),
(3,NULL,200000,'Cheque',NULL,'Pending','TXN003'),
(4,5,350000,'Bank Transfer','2025-04-15','Paid','TXN004'),
(5,5,180000,'Credit Card','2025-08-15','Paid','TXN005'),
(6,5,70000,'Cash','2025-06-10','Paid','TXN006'),
(7,NULL,150000,'Cheque',NULL,'Pending','TXN007'),
(8,5,110000,'Bank Transfer','2025-09-25','Paid','TXN008'),
(9,5,500000,'Credit Card','2025-10-15','Paid','TXN009'),
(10,5,80000,'Cash','2025-10-25','Paid','TXN010'),
(11,NULL,450000,'Bank Transfer',NULL,'Rejected','TXN011'),
(12,5,60000,'Cash','2025-12-10','Paid','TXN012'),
(13,NULL,130000,'Cheque',NULL,'Approved','TXN013'),
(14,5,170000,'Bank Transfer','2026-02-10','Paid','TXN014'),
(15,5,300000,'Credit Card','2026-03-15','Paid','TXN015'),
(16,5,95000,'Cash','2026-04-12','Paid','TXN016'),
(17,NULL,410000,'Cheque',NULL,'Pending','TXN017'),
(18,5,210000,'Bank Transfer','2026-06-12','Paid','TXN018'),
(19,5,180000,'Credit Card','2026-07-12','Paid','TXN019'),
(20,5,270000,'Bank Transfer','2026-08-12','Paid','TXN020');


