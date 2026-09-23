"""
Scenario 07 — Learning after false positive.

A bad match is reported, the feedback worker records it, and the learning
worker updates negative keywords in the Product Brain.
"""

from simulation.engine import deterministic_event, _stable_uuid


def build_steps(org_id: str):
    s = "07_false_positive_learning"
    worker = _stable_uuid(f"{s}:worker")
    run = _stable_uuid(f"{s}:run:{worker}")
    mission = _stable_uuid(f"{s}:mission")
    roas = "10000000-0000-0000-0000-000000000001"

    steps = [
        ("worker.started", 0.0, "MEMORY_LEARNING", {
            "worker_type": "feedback",
            "worker_name": "Feedback Processor #01",
            "autonomy_level": 2,
            "mission_objective": "Process human corrections into system learning",
        }),
        ("worker.verification_completed", 2.0, "MEMORY_LEARNING", {
            "claim_id": _stable_uuid(f"{s}:claim"),
            "verdict": "RESEARCH_AGAIN",
            "reason": "Human reported match as false positive: post was about organic SEO, not paid attribution.",
            "checks_performed": {"negative_keyword_hit": True},
        }),
        ("worker.learning_updated", 4.0, "MEMORY_LEARNING", {
            "learning_type": "false_positive_correction",
            "description": "Added 'organic search ranking' and 'seo backlink' to ROASSensor negative keywords.",
            "entity_type": "product_brain",
            "entity_id": roas,
            "changes": ["negative_keywords += organic search ranking", "match_threshold 0.72 -> 0.75"],
            "triggered_by": "false_positive",
        }),
        ("worker.state_changed", 4.5, "MEMORY_LEARNING", {
            "from_state": "LEARNING", "to_state": "IDLE", "reason": "learning_applied",
        }),
    ]

    return [
        deterministic_event(s, i, org_id, etype, worker, run, mission, offset, payload,
                            logical_zone=zone, logical_station="feedback_processor")
        for i, (etype, offset, zone, payload) in enumerate(steps)
    ]
