"""
Scenario 06 — Human approval action.

Drafter produces an outreach draft, requests approval (Temporal signal
pattern: workflow pauses until action_approved), then executes.
"""

from simulation.engine import deterministic_event, _stable_uuid


def build_steps(org_id: str):
    s = "06_human_approval"
    worker = _stable_uuid(f"{s}:worker")
    run = _stable_uuid(f"{s}:run:{worker}")
    mission = _stable_uuid(f"{s}:mission")
    action_id = _stable_uuid(f"{s}:action")

    steps = [
        ("worker.started", 0.0, "ACTION_CENTER", {
            "worker_type": "outreach_draft",
            "worker_name": "Outreach Drafter #03",
            "autonomy_level": 3,
            "mission_objective": "Draft outreach for high-intent leads",
        }),
        ("worker.state_changed", 1.0, "ACTION_CENTER", {
            "from_state": "IDLE", "to_state": "DRAFTING", "reason": "lead_assigned",
        }),
        ("worker.action_requested", 4.0, "ACTION_CENTER", {
            "action_type": "draft_response",
            "target_entity": "growth_hacker_88",
            "target_platform": "reddit",
            "risk_level": "medium",
        }),
        ("worker.approval_requested", 5.0, "ACTION_CENTER", {
            "action_type": "draft_response",
            "action_id": action_id,
            "draft_content": "Hi! Saw your post about Meta vs Stripe numbers mismatching — that's usually server-side tracking. We built ROASSensor for exactly this. Want a 5-min walkthrough?",
            "reason_for_approval": "autonomy_level_3_requires_human_signoff",
            "risk_level": "medium",
            "target_entity": "growth_hacker_88",
            "target_platform": "reddit",
        }),
        ("worker.state_changed", 5.2, "ACTION_CENTER", {
            "from_state": "DRAFTING", "to_state": "WAITING_APPROVAL", "reason": "human_in_the_loop",
        }),
        ("worker.action_approved", 90.0, "ACTION_CENTER", {
            "action_id": action_id, "reviewed_by": "00000000-0000-0000-0000-000000000099",
            "decision": "APPROVED",
        }),
        ("worker.state_changed", 90.2, "ACTION_CENTER", {
            "from_state": "WAITING_APPROVAL", "to_state": "EXECUTING", "reason": "approval_received",
        }),
        ("worker.action_executed", 95.0, "ACTION_CENTER", {
            "action_id": action_id, "result": "posted", "external_url": "https://reddit.com/r/ecommerce/comments/abc123/reply",
        }),
        ("worker.state_changed", 95.5, "ACTION_CENTER", {
            "from_state": "EXECUTING", "to_state": "IDLE", "reason": "action_complete",
        }),
    ]

    return [
        deterministic_event(s, i, org_id, etype, worker, run, mission, offset, payload,
                            logical_zone=zone, logical_station="outreach_station")
        for i, (etype, offset, zone, payload) in enumerate(steps)
    ]
