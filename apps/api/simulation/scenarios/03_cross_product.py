"""
Scenario 03 — Cross-product opportunity.

A signal matches a primary product AND reveals a cross-sell path to a
second portfolio product (plan G-3).
"""

from simulation.engine import deterministic_event, _stable_uuid


def build_steps(org_id: str):
    s = "03_cross_product"
    worker = _stable_uuid(f"{s}:worker")
    run = _stable_uuid(f"{s}:run:{worker}")
    mission = _stable_uuid(f"{s}:mission")
    roas = "10000000-0000-0000-0000-000000000001"
    refund = "10000000-0000-0000-0000-000000000003"

    steps = [
        ("worker.started", 0.0, "INTELLIGENCE_LAB", {
            "worker_type": "cross_sell",
            "worker_name": "Cross-Sell Analyst #01",
            "autonomy_level": 2,
            "mission_objective": "Detect cross-sell opportunities across the portfolio",
        }),
        ("worker.evidence_found", 1.5, "INTELLIGENCE_LAB", {
            "claim_statement": "Brands scaling ad spend see dispute spikes within 30 days.",
            "evidence_type": "DIRECT",
            "source_url": "https://reddit.com/r/shopify/comments/disputes",
            "evidence_quote": "Right after we scaled ads our chargebacks tripled.",
            "confidence": 0.88,
            "is_independent": True,
        }),
        ("worker.product_matched", 3.0, "INTELLIGENCE_LAB", {
            "signal_summary": "Scaling D2C brand hit by ad-fraud chargebacks",
            "primary_product_id": roas,
            "primary_product_name": "ROASSensor",
            "secondary_product_id": refund,
            "secondary_product_name": "RefundSensor",
            "cross_sell_product_id": refund,
            "cross_sell_product_name": "RefundSensor",
            "overall_score": 0.89,
            "match_components": {"problem_fit": 0.9, "persona_fit": 0.92, "industry_fit": 0.88, "intent_fit": 0.83},
            "explanation": "Primary need is attribution; the dispute spike makes RefundSensor a natural cross-sell per the CROSS_SELL relationship.",
            "match_reasons": ["primary attribution need", "dispute-rate uptick", "existing CROSS_SELL product relationship"],
        }),
        ("worker.task_transferred", 4.5, "ACTION_CENTER", {
            "to_worker_type": "outreach_draft",
            "to_worker_name": "Outreach Drafter #03",
            "task_type": "draft_cross_sell_outreach",
            "from_zone": "INTELLIGENCE_LAB",
            "to_zone": "ACTION_CENTER",
            "package_contents": {"problem": "chargeback spike after ad scaling", "confidence": 0.89},
            "priority": "high",
            "reason": "cross_sell_opportunity",
        }),
        ("worker.state_changed", 5.0, "ACTION_CENTER", {
            "from_state": "MATCHING", "to_state": "IDLE", "reason": "handoff_complete",
        }),
    ]

    return [
        deterministic_event(s, i, org_id, etype, worker, run, mission, offset, payload,
                            logical_zone=zone, logical_station="portfolio_matcher")
        for i, (etype, offset, zone, payload) in enumerate(steps)
    ]
