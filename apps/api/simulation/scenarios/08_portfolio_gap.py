"""
Scenario 08 — Portfolio gap detected.

The portfolio analyzer identifies a recurring market problem that NO product
in the portfolio covers (plan G-4).
"""

from simulation.engine import deterministic_event, _stable_uuid


def build_steps(org_id: str):
    s = "08_portfolio_gap"
    worker = _stable_uuid(f"{s}:worker")
    run = _stable_uuid(f"{s}:run:{worker}")
    mission = _stable_uuid(f"{s}:mission")

    steps = [
        ("worker.started", 0.0, "PRODUCT_CAMPUS", {
            "worker_type": "portfolio_analyzer",
            "worker_name": "Portfolio Analyzer #01",
            "autonomy_level": 2,
            "mission_objective": "Detect unmet market problems across the portfolio",
        }),
        ("worker.problem_detected", 2.0, "PRODUCT_CAMPUS", {
            "problem_statement": "Merchants repeatedly ask for automated ad-creative fatigue detection before ROAS decays.",
            "problem_category": "creative_analytics",
            "confidence": 0.81,
            "source_url": "https://reddit.com/r/PPC/comments/fatigue",
            "urgency": "medium",
        }),
        ("worker.no_product_match", 3.5, "PRODUCT_CAMPUS", {
            "signal_summary": "Ad creative fatigue detection",
            "reason": "no_portfolio_product_covers_creative_analytics",
            "considered_products": ["10000000-0000-0000-0000-000000000001"],
        }),
        ("worker.portfolio_gap_detected", 5.0, "PRODUCT_CAMPUS", {
            "problem_description": "Automated ad-creative fatigue detection ahead of ROAS decay",
            "volume": 38,
            "growth_rate": 0.44,
            "audience": "Performance marketing managers",
            "industries": ["E-commerce", "D2C"],
            "competing_products": ["Motion", "AdCreative.ai"],
            "portfolio_coverage_score": 0.05,
            "opportunity_score": 0.78,
        }),
        ("worker.state_changed", 5.5, "PRODUCT_CAMPUS", {
            "from_state": "ANALYZING", "to_state": "IDLE", "reason": "gap_reported",
        }),
    ]

    return [
        deterministic_event(s, i, org_id, etype, worker, run, mission, offset, payload,
                            logical_zone=zone, logical_station="opportunity_detector")
        for i, (etype, offset, zone, payload) in enumerate(steps)
    ]
