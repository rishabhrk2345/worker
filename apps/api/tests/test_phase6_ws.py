"""
apps/api/tests/test_phase6_ws.py

Phase 6 verification:
- Subscription ack protocol
- Server-side _matches() filter logic (unit-tested directly)
- Invalid JSON gets error reply
- Queue and bus integration (fast path only)
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from core.event_publisher import set_default_bus
from core.event_bus import InMemoryEventBus
from routers.ws import _matches


# ── Subscription filter unit tests (no I/O) ──────────────────────────────────

def test_matches_no_filter():
    """Empty filter → everything passes."""
    event = {"mission_id": "m1", "worker_id": "w1", "logical_zone": "RESEARCH_LAB"}
    assert _matches(event, {}) is True


def test_matches_mission_filter_pass():
    event = {"mission_id": "mission-A", "worker_id": "w1"}
    assert _matches(event, {"mission_ids": ["mission-A", "mission-B"]}) is True


def test_matches_mission_filter_fail():
    """Event for mission-B is blocked when subscribed to mission-A only."""
    event = {"mission_id": "mission-B", "worker_id": "w1"}
    assert _matches(event, {"mission_ids": ["mission-A"]}) is False


def test_matches_worker_filter_pass():
    event = {"mission_id": "m1", "worker_id": "w42"}
    assert _matches(event, {"worker_ids": ["w42"]}) is True


def test_matches_worker_filter_fail():
    event = {"mission_id": "m1", "worker_id": "w99"}
    assert _matches(event, {"worker_ids": ["w42"]}) is False


def test_matches_zone_filter_pass():
    event = {"logical_zone": "RESEARCH_LAB"}
    assert _matches(event, {"zones": ["RESEARCH_LAB", "INTELLIGENCE_LAB"]}) is True


def test_matches_zone_filter_fail():
    event = {"logical_zone": "ACTION_CENTER"}
    assert _matches(event, {"zones": ["RESEARCH_LAB"]}) is False


def test_matches_combined_all_pass():
    event = {"mission_id": "m1", "worker_id": "w1", "logical_zone": "RESEARCH_LAB"}
    assert _matches(event, {
        "mission_ids": ["m1"],
        "worker_ids": ["w1"],
        "zones": ["RESEARCH_LAB"],
    }) is True


def test_matches_combined_one_fail():
    """All filters match except zone — should block."""
    event = {"mission_id": "m1", "worker_id": "w1", "logical_zone": "ACTION_CENTER"}
    assert _matches(event, {
        "mission_ids": ["m1"],
        "worker_ids": ["w1"],
        "zones": ["RESEARCH_LAB"],
    }) is False


# ── WebSocket protocol tests ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_bus():
    bus = InMemoryEventBus()
    set_default_bus(bus)
    yield bus
    set_default_bus(InMemoryEventBus())


def test_subscription_ack(clean_bus):
    """Sending a subscribe message gets a subscribed ack back immediately."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/events/org-test") as ws:
            ws.send_json({"subscribe": {"mission_ids": ["mission-A"]}})
            ack = ws.receive_json()
            assert ack["type"] == "subscribed"
            assert ack["filters"]["mission_ids"] == ["mission-A"]


def test_subscription_update_ack(clean_bus):
    """Sending a second subscribe replaces the filter and acks again."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/events/org-test") as ws:
            ws.send_json({"subscribe": {"mission_ids": ["m1"]}})
            ack1 = ws.receive_json()
            assert ack1["filters"]["mission_ids"] == ["m1"]

            ws.send_json({"subscribe": {"mission_ids": ["m2"]}})
            ack2 = ws.receive_json()
            assert ack2["filters"]["mission_ids"] == ["m2"]


def test_invalid_json_gets_error_reply(clean_bus):
    """Sending non-JSON text gets an error response."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/events/org-ws-err") as ws:
            ws.send_text("this is not json {{")
            reply = ws.receive_json()
            assert reply["type"] == "error"
