"""
apps/api/tests/test_phase6_ws.py

Phase 6 verification (plan Part 10):
- Subscription protocol: client subscribes with filters -> server acks
- Server-side filtering: a client subscribed to mission A receives no
  mission B events (plan L-2)
"""

import pytest
from fastapi.testclient import TestClient

from core.event_publisher import get_default_bus


@pytest.fixture
def ws_client():
    from main import app

    client = TestClient(app)
    with client:
        yield client


def test_subscription_filter_only_receives_matching(ws_client):
    bus = get_default_bus()
    org = "org-ws-test"

    with ws_client.websocket_connect(f"/ws/events/{org}") as ws:
        # 1. Subscribe to mission-A only
        ws.send_json({"subscribe": {"mission_ids": ["mission-A"]}})
        ack = ws.receive_json()
        assert ack["type"] == "subscribed"
        assert ack["filters"] == {"mission_ids": ["mission-A"]}

        # 2. Publish one non-matching (mission-B) and three matching (mission-A)
        portal = ws_client.portal
        for i, mission in enumerate(["mission-B", "mission-A", "mission-A", "mission-A"]):
            portal.start_task_soon(
                bus.publish,
                f"org:{org}",
                {
                    "event_type": "worker.state_changed",
                    "worker_id": f"w{i}",
                    "worker_run_id": "run-1",
                    "mission_id": mission,
                    "sequence": i,
                    "payload": {},
                },
            )

        # 3. First delivered batch must contain ONLY mission-A events
        message = ws.receive_json()
        assert message["type"] == "events"
        missions = {e["mission_id"] for e in message["events"]}
        assert missions == {"mission-A"}


def test_invalid_json_gets_error_reply(ws_client):
    with ws_client.websocket_connect("/ws/events/org-ws-err") as ws:
        ws.send_text("this is not json")
        reply = ws.receive_json()
        assert reply["type"] == "error"
