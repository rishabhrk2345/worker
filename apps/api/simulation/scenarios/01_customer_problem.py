"""
Scenario 01 — New customer problem discovered.

Deterministic worker flow: started -> source opened -> search -> page fetched
-> content found -> problem detected -> product matched (ROASSensor).
"""

from simulation.engine import deterministic_event, _stable_uuid

ORG_PRODUCTS = {
    "roassensor": "10000000-0000-0000-0000-000000000001",
}


def build_steps(org_id: str):
    s = "01_customer_problem"
    worker = _stable_uuid(f"{s}:worker")
    run = _stable_uuid(f"{s}:run:{worker}")
    mission = _stable_uuid(f"{s}:mission")

    steps = [
        ("worker.started", 0.0, "DISCOVERY_CITY", {
            "worker_type": "social_discovery",
            "worker_name": "YouTube Crawler #01",
            "autonomy_level": 2,
            "mission_objective": "Discover emerging customer problems in YouTube marketing & ecommerce videos",
            "assigned_products": [ORG_PRODUCTS["roassensor"]],
        }),
        ("worker.state_changed", 0.5, "DISCOVERY_CITY", {
            "from_state": "IDLE", "to_state": "DISCOVERING", "reason": "mission_start",
        }),
        ("worker.source_opened", 1.0, "DISCOVERY_CITY", {
            "platform": "youtube", "source_name": "YouTube",
            "source_station_id": "youtube_station",
            "query": "facebook ads not matching stripe revenue attribution",
            "query_type": "problem_phrase",
            "reason": "icp_keyword_match",
        }),
        ("worker.search_started", 2.0, "DISCOVERY_CITY", {
            "platform": "youtube", "query": "facebook ads not matching stripe revenue attribution",
        }),
        ("worker.page_fetched", 4.0, "DISCOVERY_CITY", {
            "url": "https://www.youtube.com/watch?v=roas_abc123",
            "http_status": 200,
        }),
        ("worker.content_found", 5.0, "DISCOVERY_CITY", {
            "url": "https://www.youtube.com/watch?v=roas_abc123",
            "content_type": "youtube_comment",
            "author": "growth_hacker_88",
        }),
        ("worker.problem_detected", 6.0, "DISCOVERY_CITY", {
            "problem_statement": "Meta Ads Manager reports 3x ROAS but Stripe revenue shows 1.2x — cannot trust attribution",
            "problem_category": "attribution_discrepancy",
            "confidence": 0.93,
            "source_url": "https://www.youtube.com/watch?v=roas_abc123",
            "evidence_quote": "Facebook says we made 3x but our bank account says 1.2x. Which do we trust for scaling?",
            "urgency": "high",
        }),
        ("worker.state_changed", 6.5, "INTELLIGENCE_LAB", {
            "from_state": "DISCOVERING", "to_state": "MATCHING", "reason": "problem_detected",
        }),
        ("worker.product_matched", 7.5, "INTELLIGENCE_LAB", {
            "signal_summary": "Meta/Stripe ROAS attribution discrepancy found in YouTube comment thread",
            "primary_product_id": ORG_PRODUCTS["roassensor"],
            "primary_product_name": "ROASSensor",
            "overall_score": 0.94,
            "match_components": {"problem_fit": 0.97, "persona_fit": 0.9, "industry_fit": 0.95, "intent_fit": 0.9},
            "explanation": "YouTube comment describes exactly the Meta-vs-Stripe attribution mismatch ROASSensor resolves via server-side CAPI.",
            "match_reasons": ["attribution discrepancy keyword match", "D2C e-commerce persona match"],
            "non_match_reasons": [],
        }),
        ("worker.state_changed", 8.0, "DISCOVERY_CITY", {
            "from_state": "MATCHING", "to_state": "IDLE", "reason": "task_complete",
        }),
    ]

    events = []
    for i, (etype, offset, zone, payload) in enumerate(steps):
        events.append(deterministic_event(
            s, i, org_id, etype, worker, run, mission, offset, payload,
            logical_zone=zone, logical_station="social_crawler_bay",
        ))
    return events
