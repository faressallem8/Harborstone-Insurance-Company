"""
Fixed evaluation suite for the Harborstone Planning Agent.

The same test suite is reused across every planning algorithm
to ensure fair comparison.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PlanningTestCase:
    """
    Represents one evaluation scenario.

    Attributes
    ----------
    id
        Unique test identifier.

    title
        Short human-readable name.

    goal
        User request given to the planning agent.

    expected_tools
        MCP tools expected to appear during execution.

    expected_best_method
        Algorithm that is expected to perform best.
        (Used only for documentation/comparison.)

    requires_grounding
        Whether real EnvironmentFeedback is important.

    notes
        Why this case exists.
    """

    id: str
    title: str
    goal: str

    expected_tools: list[str]

    expected_best_method: str

    requires_grounding: bool

    notes: str


TEST_CASES = [

    PlanningTestCase(
        id="TC01",

        title="Policy Lookup",

        goal=(
            "Retrieve the policy details for policy 1001 "
            "and summarize the customer's coverage."
        ),

        expected_tools=[
            "get_policy_details",
        ],

        expected_best_method="Plan-and-Solve",

        requires_grounding=False,

        notes="Simple deterministic lookup."
    ),

    PlanningTestCase(
        id="TC02",

        title="Claim Investigation",

        goal=(
            "Investigate claim 205 by checking the claim status, "
            "retrieving the customer information, retrieving the "
            "policy details, then summarize the findings."
        ),

        expected_tools=[
            "check_claim_status",
            "get_customer_info",
            "get_policy_details",
        ],

        expected_best_method="Decomposition",

        requires_grounding=False,

        notes="Requires multiple dependent subtasks."
    ),

    PlanningTestCase(
        id="TC03",

        title="Risk Assessment",

        goal=(
            "Assess the insurance risk for policy 305 "
            "and explain whether additional review is recommended."
        ),

        expected_tools=[
            "assess_risk",
        ],

        expected_best_method="Tree-of-Thoughts",

        requires_grounding=False,

        notes="Benefits from exploring multiple reasoning paths."
    ),

    PlanningTestCase(
        id="TC04",

        title="Claim Approval Decision",

        goal=(
            "Investigate claim 410 and determine whether "
            "the claim should be approved."
        ),

        expected_tools=[
            "check_claim_status",
            "get_policy_details",
            "assess_risk",
            "approve_claim",
        ],

        expected_best_method="LATS",

        requires_grounding=True,

        notes="High-impact decision requiring grounded evaluation."
    ),

    PlanningTestCase(
        id="TC05",

        title="Fraud Investigation",

        goal=(
            "Investigate claim 512 for possible fraud "
            "before approving the claim."
        ),

        expected_tools=[
            "check_claim_status",
            "assess_risk",
            "approve_claim",
        ],

        expected_best_method="LATS",

        requires_grounding=True,

        notes="Grounded feedback should detect fraud indicators."
    ),

    PlanningTestCase(
        id="TC06",

        title="Invalid Claim Recovery",

        goal=(
            "Investigate claim 999999. "
            "If the claim cannot be found, "
            "adapt the investigation and report the failure."
        ),

        expected_tools=[
            "check_claim_status",
        ],

        expected_best_method="Dynamic Decomposition",

        requires_grounding=True,

        notes="Designed to demonstrate divergence and Reflexion."
    ),
]