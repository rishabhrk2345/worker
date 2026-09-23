"""
Scenario 04 — Market trend spike.

Trend discovery worker detects anomalous mention volume for a topic.
"""

from simulation.engine import deterministic_event, _stable_uuid


def build_steps(org_id: str):
    s = "04_trend_spike"
    worker = _stable_uuid(f"{s}:worker")
    run = _stable_uuid(f"{s}:run:{worker}")
    mission = _stable_uuid(f"{s}:mission")

    steps = [
        ("worker.started", 0.0, "DISCOVERY_CITY", {
            "worker_type": "trend_discovery",
            "worker_name": "Trend Scout #02",
            "autonomy_level": 2,
            "mission_objective": "Detect anomalous market topic growth",
        }),
        ("worker.search_started", 1.0, "DISCOVERY_CITY", {
            "platform": "news", "query": "server-side tracking adoption",
        }),
        ("worker.anomaly_detected", 3.5, "DISCOVERY_CITY", {
            "topic": "server-side tracking",
            "baseline_mentions_7d": 42,
            "current_mentions_24h": 61,
            "growth_rate": 0.92,
            "anomaly_type": "mention_spike",
        }),
        ("worker.content_found", 4.5, "DISCOVERY_CITY", {
            "url": "https://news.ycombinator.com/item?id=39482910",
            "content_type": "hn_thread",
        }),
        ("worker.state_changed", 5.0, "DISCOVERY_CITY", {
            "from_state": "SEARCHING", "to_state": "IDLE", "reason": "trend_reported",
        }),
    ]

    return [
        deterministic_event(s, i, org_id, etype, worker, run, mission, offset, payload,
                            logical_zone=zone, logical_station="web_crawler_bay")
        for i, (etype, offset, zone, payload) in enumerate(steps)
    ]
