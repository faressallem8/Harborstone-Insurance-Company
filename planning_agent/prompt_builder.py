# planning_agent/prompt_builder.py
"""
Builds task descriptions for the planning algorithms.
"""

from typing import Dict, Any, List


def build_plan_and_solve_prompt(sub_task: Dict[str, Any]) -> str:
    """Build a prompt for Plan-and-Solve."""
    task_type = sub_task.get("type", "unknown")
    params = sub_task.get("params", {})

    if task_type == "fetch_claim":
        return f"""
Task: Fetch claim details for claim ID {params.get('claim_id', 1)}.
Output: The complete claim information including amount, status, and customer.
"""

    elif task_type == "fetch_policy":
        return f"""
Task: Fetch policy details for policy ID {params.get('policy_id', 1)}.
Output: The complete policy information including coverage, limits, and customer.
"""

    elif task_type == "fetch_customer":
        return f"""
Task: Fetch customer details for customer ID {params.get('customer_id', 1)}.
Output: The complete customer information including name, contact, and status.
"""

    else:
        return f"""
Task: {task_type}
Parameters: {params}
Execute this task and return the result.
"""


def build_tree_of_thoughts_problem(sub_task: Dict[str, Any]) -> str:
    """Build a problem description for Tree of Thoughts."""
    task_type = sub_task.get("type", "unknown")
    params = sub_task.get("params", {})

    if task_type == "rank_by_urgency":
        claim_ids = params.get("claim_ids", [1, 2, 3])
        return f"""
Rank these claims by urgency: {claim_ids}

Consider:
- Claim amount (higher = more urgent)
- Claim age (older = more urgent)
- Policy type (commercial = more urgent)
- Customer status (active = more urgent)

Output: A ranked list from most urgent to least urgent, with justification for each position.
"""

    elif task_type == "assess_risk":
        policy_id = params.get("policy_id", 1)
        return f"""
Assess the risk for policy {policy_id}.

Consider:
- Vessel age (older = higher risk)
- Vessel type (fishing = higher risk)
- Claim history (multiple claims = higher risk)
- Coverage amount (higher = higher risk)

Output: Risk level (Low/Medium/High) with justification and recommendations.
"""

    elif task_type == "evaluate_options":
        options = params.get("options", ["Option A", "Option B", "Option C"])
        return f"""
Evaluate these options: {options}

Consider:
- Feasibility
- Cost
- Time
- Risk

Output: Ranking of options with scores and justifications.
"""

    else:
        return f"""
Task: {task_type}
Parameters: {params}
Generate and evaluate multiple candidate solutions, selecting the best one.
"""


def build_lats_task(sub_task: Dict[str, Any]) -> str:
    """Build a task description for LATS."""
    task_type = sub_task.get("type", "unknown")
    params = sub_task.get("params", {})

    if task_type == "make_decision":
        claim_id = params.get("claim_id", 1)
        return f"""
Decision: Should claim {claim_id} be approved or denied?

You must make a decision based on:
1. Claim details (amount, type, age)
2. Policy details (coverage, limits, customer)
3. Customer history (previous claims, status)
4. Fraud indicators (suspicious patterns)

Output: A decision (approved or denied) with comprehensive justification.
"""

    elif task_type == "investigate_fraud":
        claim_id = params.get("claim_id", 1)
        return f"""
Investigate claim {claim_id} for potential fraud.

Check for:
1. Multiple claims on the same policy
2. Unusual claim amounts
3. Suspicious patterns in claim history
4. Policy violations

Output: Fraud risk assessment (Low/Medium/High) with recommended action.
"""

    elif task_type == "check_fraud_indicators":
        claim_id = params.get("claim_id", 1)
        return f"""
Check claim {claim_id} for fraud indicators.

Verify:
1. Claim amount is within normal range
2. No duplicate claims on same policy
3. Claim type matches policy coverage
4. Incident date is reasonable

Output: Fraud assessment with confidence score and recommendation.
"""

    else:
        return f"""
Task: {task_type}
Parameters: {params}
Make an optimal decision based on available information and constraints.
"""


def build_self_refine_prompt(sub_task: Dict[str, Any]) -> str:
    """Build a prompt for Self-Refine."""
    task_type = sub_task.get("type", "unknown")
    params = sub_task.get("params", {})

    if task_type == "generate_justification":
        claim_id = params.get("claim_id", 1)
        decision = params.get("decision", "approved")
        return f"""
Generate a professional justification for {decision} claim {claim_id}.

The justification should include:
1. Summary of the claim
2. Key factors considered
3. Rationale for the decision
4. Any conditions or caveats

Make it clear, concise, and professional.
"""

    else:
        return f"""
Task: {task_type}
Parameters: {params}
Generate a well-structured output for this task.
"""