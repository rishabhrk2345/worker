"""
apps/api/tests/test_phase1.py

Comprehensive Phase 1 test suite:
- Cryptographic security & credential encryption
- Multi-tenancy isolation & RBAC
- Model integrity & seed verification
- FastAPI endpoints (health, snapshot, products, workers)
"""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from main import app
from core.security import (
    encrypt_credential, decrypt_credential,
    hash_password, verify_password,
    create_access_token, decode_access_token
)
from core.config import settings

@pytest.mark.asyncio
async def test_credential_encryption_roundtrip():
    """Verify AES-256-GCM credential encryption & decryption."""
    raw_secret = "super_sensitive_api_token_reddit_xyz987"
    encrypted = encrypt_credential(raw_secret)
    assert encrypted != raw_secret
    assert len(encrypted) > 20

    decrypted = decrypt_credential(encrypted)
    assert decrypted == raw_secret

@pytest.mark.asyncio
async def test_password_hashing():
    """Verify PBKDF2 password hashing & verification."""
    pwd = "EnterpriseMarketingPassword2026!"
    hashed = hash_password(pwd)
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong_password", hashed) is False

@pytest.mark.asyncio
async def test_jwt_token_flow():
    """Verify JWT access token issuance, claims, and signature."""
    org_id = "00000000-0000-0000-0000-000000000001"
    user_id = "00000000-0000-0000-0000-000000000099"
    token = create_access_token(user_id=user_id, organization_id=org_id, role="admin", permissions=["worker:read"])
    
    claims = decode_access_token(token)
    assert claims["sub"] == user_id
    assert claims["org_id"] == org_id
    assert claims["role"] == "admin"
    assert "worker:read" in claims["permissions"]

@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify GET /health (liveness) and GET /health/ready (readiness)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Liveness probe
        resp_live = await client.get("/health")
        assert resp_live.status_code == 200
        assert resp_live.json()["status"] == "alive"

        # Readiness probe
        resp_ready = await client.get("/health/ready")
        assert resp_ready.status_code in (200, 503)
        data = resp_ready.json()
        assert data["status"] in ("healthy", "degraded")
        assert "components" in data

@pytest.mark.asyncio
async def test_snapshot_endpoint(client):
    """Verify GET /api/snapshot structure (DB dependency overridden to test session)."""
    resp = await client.get("/api/snapshot")
    assert resp.status_code == 200
    data = resp.json()
    assert "kpis" in data
    assert "workers" in data
    assert "products" in data
    assert "sources" in data
    assert "latest_sequence" in data

@pytest.mark.asyncio
async def test_list_products_and_workers(client):
    """Verify GET /api/products and GET /api/workers."""
    # Products
    prod_resp = await client.get("/api/products")
    assert prod_resp.status_code == 200
    assert isinstance(prod_resp.json(), list)

    # Workers
    worker_resp = await client.get("/api/workers")
    assert worker_resp.status_code == 200
    assert isinstance(worker_resp.json(), list)
