"""
Scenario 02 — Competitor feature launch detected.

War Room flow: competitor watcher notices pricing/feature change on a
competitor website and publishes a competitor event.
"""

from simulation.engine import deterministic_event, _stable_uuid


def build_steps(org_id: str):
    s = "02_competitor_launch"
    worker = _stable_uuid(f"{s}:worker")
    run = _stable_uuid(f"{s}:run:{worker}")
    mission = _stable_uuid(f"{s}:mission")

    steps = [
        ("worker.started", 0.0, "COMPETITOR_WAR_ROOM", {
            "worker_type": "competitor_discovery",
            "worker_name": "Competitor Watcher #01",
            "autonomy_level": 2,
            "mission_objective": "Monitor competitor websites for product and pricing changes",
        }),
        ("worker.source_opened", 1.0, "COMPETITOR_WAR_ROOM", {
            "platform": "web", "source_name": "Public Web Pages",
            "query": "triplewhale.com/changelog",
            "reason": "scheduled_competitor_scan",
        }),
        ("worker.page_fetched", 2.5, "COMPETITOR_WAR_ROOM", {
            "url": "https://triplewhale.com/changelog",
            "http_status": 200,
        }),
        ("worker.state_changed", 3.0, "COMPETITOR_WAR_ROOM", {
            "from_state": "FETCHING", "to_state": "ANALYZING", "reason": "content_diff_detected",
        }),
        ("worker.competitor_event_detected", 5.0, "COMPETITOR_WAR_ROOM", {
            "competitor_name": "Triple Whale",
            "event_type": "feature_launch",
            "description": "Triple Whale launched an AI-driven creative scoring module.",
            "source_url": "https://triplewhale.com/changelog",
            "impact_score": 0.72,
        }),
        ("worker.state_changed", 5.5, "COMPETITOR_WAR_ROOM", {
            "from_state": "ANALYZING", "to_state": "IDLE", "reason": "scan_complete",
        }),
    ]

    return [
        deterministic_event(s, i, org_id, etype, worker, run, mission, offset, payload,
                            logical_zone=zone, logical_station="pricing_watch")
        for i, (etype, offset, zone, payload) in enumerate(steps)
    ]
