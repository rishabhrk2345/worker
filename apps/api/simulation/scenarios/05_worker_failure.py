"""
Scenario 05 — Worker failure and recovery.

A fetcher hits repeated failures, transitions RATE_LIMITED -> FAILED, and is
reset to IDLE by the supervisor (plan E-2/E-3 recovery semantics).
"""

from simulation.engine import deterministic_event, _stable_uuid


def build_steps(org_id: str):
    s = "05_worker_failure"
    worker = _stable_uuid(f"{s}:worker")
    run = _stable_uuid(f"{s}:run:{worker}")
    mission = _stable_uuid(f"{s}:mission")

    steps = [
        ("worker.started", 0.0, "DISCOVERY_CITY", {
            "worker_type": "web_discovery",
            "worker_name": "Web Discovery #07",
            "autonomy_level": 2,
            "mission_objective": "Fetch and parse competitor documentation pages",
        }),
        ("worker.page_fetched", 1.5, "DISCOVERY_CITY", {
            "url": "https://competitor.example.com/pricing", "http_status": 403,
        }),
        ("worker.rate_limited", 3.0, "DISCOVERY_CITY", {
            "platform": "web", "reason": "http_403_repeated", "backoff_seconds": 30,
        }),
        ("worker.state_changed", 3.2, "DISCOVERY_CITY", {
            "from_state": "FETCHING", "to_state": "RATE_LIMITED", "reason": "http_403_repeated",
        }),
        ("worker.failed", 34.0, "DISCOVERY_CITY", {
            "error": "Upstream unavailable after backoff", "attempt": 3, "will_retry": True,
        }),
        ("worker.state_changed", 34.2, "DISCOVERY_CITY", {
            "from_state": "RATE_LIMITED", "to_state": "FAILED", "reason": "retries_exhausted",
        }),
        ("worker.state_changed", 40.0, "DISCOVERY_CITY", {
            "from_state": "FAILED", "to_state": "IDLE", "reason": "supervisor_reset_for_reassignment",
        }),
    ]

    return [
        deterministic_event(s, i, org_id, etype, worker, run, mission, offset, payload,
                            logical_zone=zone, logical_station="web_crawler_bay")
        for i, (etype, offset, zone, payload) in enumerate(steps)
    ]
