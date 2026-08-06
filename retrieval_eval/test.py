# retrieval_eval/test_questions.py
QUESTIONS = [
    # Category 1: General (Naive should handle)
    {
        "id": "Q1",
        "category": "general",
        "text": "What is the standard deductible for a vessel that is 22 years old?",
        "expected_keyword": "$2,500"
    },
    {
        "id": "Q2",
        "category": "general",
        "text": "What is the premium basis for commercial fishing vessels?",
        "expected_keyword": "2.5%"
    },
    {
        "id": "Q3",
        "category": "general",
        "text": "Within how many days must a claim be filed after an incident?",
        "expected_keyword": "30 days"
    },
    {
        "id": "Q4",
        "category": "general",
        "text": "What is the coverage limit for standard policies?",
        "expected_keyword": "$250,000"
    },

    # Category 2: Citation-Heavy / Exact Identifiers (Hybrid should win)
    {
        "id": "Q5",
        "category": "citation",
        "text": "What does Section 4.2b say about cardiac-risk vessels?",
        "expected_keyword": "compression test"
    },
    {
        "id": "Q6",
        "category": "citation",
        "text": "What are the premium adjustments listed in Section 2.2 for vessels over 20 years?",
        "expected_keyword": "+1.0%"
    },
    {
        "id": "Q7",
        "category": "citation",
        "text": "According to the manual, what is the policy term limit for a cardiac-risk vessel?",
        "expected_keyword": "6 months"
    },
    {
        "id": "Q8",
        "category": "citation",
        "text": "What does the compliance section say about appeals timeframe?",
        "expected_keyword": "15 business days"
    },

    # Category 3: Multi-Hop / Decomposition (Agentic RAG should excel)
    {
        "id": "Q9",
        "category": "multi_hop",
        "text": "For a 15-year-old commercial fishing vessel with a $150,000 policy, what pre-screening and premium surcharges apply?",
        "expected_keyword": "cardiac risk" # or "engine compression"
    },
    {
        "id": "Q10",
        "category": "multi_hop",
        "text": "If a vessel is 18 years old and had two engine failures in the last year, what underwriting conditions must be met?",
        "expected_keyword": "6 months"
    },
    {
        "id": "Q11",
        "category": "multi_hop",
        "text": "What deductible applies to a 25-year-old vessel, and what additional inspection is required?",
        "expected_keyword": "dry-dock"
    },
    {
        "id": "Q12",
        "category": "multi_hop",
        "text": "A $45,000 claim is filed on a fishing vessel. Who must approve it, and what fraud indicators should be checked?",
        "expected_keyword": "Underwriter"
    },
]