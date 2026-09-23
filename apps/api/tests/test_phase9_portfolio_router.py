"""
apps/api/tests/test_phase9_portfolio_router.py

Phase 9 verification:
- PortfolioRouter scores products against signals
- Correct product matching (e.g. ROASSensor)
- Hard exclusion via problems_not_solved
- Negative keyword exclusion
- Cross-sell product recommendation
- Portfolio gap detection when no product matches
- REST API /api/intelligence/match and /api/intelligence/gaps
"""

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import Organization, Product, ProductBrain, ProductRelationship, PortfolioGap, Signal
from services.portfolio_router import PortfolioRouter
from core.security import create_access_token


# ── Helpers ─────────────────────────────────────────────────────────────────

def make_org(slug_suffix: str = "") -> Organization:
    return Organization(
        id=str(uuid.uuid4()),
        name="Test Corp",
        slug=f"test-corp-{slug_suffix or uuid.uuid4().hex[:6]}",
    )


def make_product(org_id: str, name: str, slug: str) -> Product:
    return Product(
        id=str(uuid.uuid4()),
        organization_id=org_id,
        name=name,
        slug=slug,
        description=f"{name} description",
        status="active",
    )


def make_brain(product_id: str, **kwargs) -> ProductBrain:
    defaults = {
        "problems_solved": [],
        "problems_not_solved": [],
        "keywords": [],
        "personas": [],
        "industries": [],
        "customer_language": [],
        "negative_keywords": [],
    }
    defaults.update(kwargs)
    return ProductBrain(product_id=product_id, **defaults)


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_portfolio_router_correct_match(test_db: AsyncSession):
    """ROASSensor should match a Facebook ROAS signal."""
    org = make_org()
    test_db.add(org)

    p1 = make_product(org.id, "ROASSensor", "roas-sensor")
    test_db.add(p1)
    b1 = make_brain(
        p1.id,
        problems_solved=["Facebook ROAS reporting discrepancy", "Stripe revenue attribution mismatch"],
        keywords=["roas", "attribution", "facebook ads", "stripe"],
        personas=["Head of Growth", "Performance Marketer"],
        industries=["e-commerce", "dtc"],
        problems_not_solved=["B2B sales pipeline tracking"],
        negative_keywords=["b2b", "salesforce"],
    )
    test_db.add(b1)

    # Decoy product — should NOT match
    p2 = make_product(org.id, "SupportAI", "support-ai")
    test_db.add(p2)
    b2 = make_brain(
        p2.id,
        problems_solved=["Customer ticket resolution backlog"],
        keywords=["support", "tickets", "zendesk"],
        personas=["Head of Support"],
        industries=["saas"],
    )
    test_db.add(b2)
    await test_db.commit()

    router = PortfolioRouter()
    matches = await router.route(
        test_db,
        organization_id=org.id,
        signal_id=str(uuid.uuid4()),
        signal_text="My Facebook ROAS does not match Stripe revenue attribution in our Shopify store",
        signal_meta={"industry": "e-commerce", "persona": "Head of Growth"},
        intent_score=0.9,
    )

    assert len(matches) > 0
    top = matches[0]
    assert top.product_id == p1.id
    assert top.product_name == "ROASSensor"
    assert top.overall_score >= 0.35
    assert top.problem_fit > 0.0


@pytest.mark.asyncio
async def test_portfolio_router_hard_exclusion(test_db: AsyncSession):
    """Signal that matches problems_not_solved should produce zero matches."""
    org = make_org()
    test_db.add(org)

    p1 = make_product(org.id, "ROASSensor", "roas-excl")
    test_db.add(p1)
    b1 = make_brain(
        p1.id,
        problems_solved=["Ad tracking and ROAS reporting"],
        keywords=["tracking", "roas"],
        problems_not_solved=["B2B sales pipeline tracking"],
    )
    test_db.add(b1)
    await test_db.commit()

    router = PortfolioRouter()
    matches = await router.route(
        test_db,
        organization_id=org.id,
        signal_id=str(uuid.uuid4()),
        signal_text="Looking for B2B sales pipeline tracking software for enterprise",
    )

    matched_ids = [m.product_id for m in matches]
    assert p1.id not in matched_ids


@pytest.mark.asyncio
async def test_portfolio_router_negative_keywords(test_db: AsyncSession):
    """Signal containing a negative keyword should produce zero matches."""
    org = make_org()
    test_db.add(org)

    p1 = make_product(org.id, "ROASSensor", "roas-neg")
    test_db.add(p1)
    b1 = make_brain(
        p1.id,
        problems_solved=["Ad tracking"],
        keywords=["ad", "tracking"],
        negative_keywords=["crypto", "web3"],
    )
    test_db.add(b1)
    await test_db.commit()

    router = PortfolioRouter()
    matches = await router.route(
        test_db,
        organization_id=org.id,
        signal_id=str(uuid.uuid4()),
        signal_text="Ad tracking for crypto token launch web3 project",
    )
    assert len(matches) == 0


@pytest.mark.asyncio
async def test_portfolio_router_gap_detection(test_db: AsyncSession):
    """When no product matches, a PortfolioGap record should be created."""
    org = make_org()
    test_db.add(org)
    await test_db.commit()

    router = PortfolioRouter()
    problem = "Inventory barcode scanner synchronization with QuickBooks offline"
    matches = await router.route(
        test_db,
        organization_id=org.id,
        signal_id=str(uuid.uuid4()),
        signal_text=problem,
    )

    assert len(matches) == 0

    result = await test_db.execute(
        select(PortfolioGap).where(PortfolioGap.organization_id == org.id)
    )
    gaps = result.scalars().all()
    assert len(gaps) == 1
    assert gaps[0].problem_description == problem
    assert gaps[0].volume == 1


@pytest.mark.asyncio
async def test_portfolio_router_cross_sell(test_db: AsyncSession):
    """Primary match should carry cross_sell_product_id from ProductRelationship."""
    org = make_org()
    test_db.add(org)

    p1 = make_product(org.id, "ROASSensor", "roas-cross")
    p2 = make_product(org.id, "RevenueSensor", "rev-cross")
    test_db.add_all([p1, p2])

    b1 = make_brain(p1.id, problems_solved=["ROAS discrepancy"], keywords=["roas", "ad spend"])
    b2 = make_brain(p2.id, problems_solved=["Revenue leak"], keywords=["revenue", "mrr"])
    test_db.add_all([b1, b2])

    # ProductRelationship has no organization_id column — only product_a_id, product_b_id
    rel = ProductRelationship(
        product_a_id=p1.id,
        product_b_id=p2.id,
        relationship_type="CROSS_SELL",
    )
    test_db.add(rel)
    await test_db.commit()

    router = PortfolioRouter()
    matches = await router.route(
        test_db,
        organization_id=org.id,
        signal_id=str(uuid.uuid4()),
        signal_text="ROAS discrepancy on marketing campaigns ad spend waste",
    )

    assert len(matches) > 0
    assert matches[0].product_id == p1.id
    assert matches[0].cross_sell_product_id == p2.id


@pytest.mark.asyncio
async def test_off_topic_signal_no_match(test_db: AsyncSession):
    """A completely unrelated signal should produce no matches."""
    org = make_org()
    test_db.add(org)

    p1 = make_product(org.id, "ROASSensor", "roas-offtopic")
    test_db.add(p1)
    b1 = make_brain(
        p1.id,
        problems_solved=["ROAS optimization"],
        keywords=["roas", "attribution"],
        negative_keywords=["plumbing", "construction"],
    )
    test_db.add(b1)
    await test_db.commit()

    router = PortfolioRouter()
    matches = await router.route(
        test_db,
        organization_id=org.id,
        signal_id=str(uuid.uuid4()),
        signal_text="Best plumbing fixtures for commercial construction projects",
    )
    assert len(matches) == 0


@pytest.mark.asyncio
async def test_intelligence_match_api(client, test_db: AsyncSession):
    """POST /api/intelligence/match returns a list of MatchResult objects."""
    org = make_org()
    test_db.add(org)

    p1 = make_product(org.id, "ROASSensor", "roas-api")
    test_db.add(p1)
    b1 = make_brain(
        p1.id,
        problems_solved=["ROAS optimization and tracking"],
        keywords=["roas", "tracking", "facebook"],
        customer_language=["ROAS does not match"],
    )
    test_db.add(b1)
    await test_db.commit()

    token = create_access_token(
        user_id=str(uuid.uuid4()),
        organization_id=org.id,
        role="admin",
        permissions=["*"],
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/intelligence/match",
        headers=headers,
        json={
            "problem_statement": "ROAS optimization for Facebook ads",
            "intent_score": 0.85,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # Endpoint returns a plain list (not wrapped in {"matches": ...})
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["product_id"] == p1.id


@pytest.mark.asyncio
async def test_intelligence_gaps_api(client, test_db: AsyncSession):
    """GET /api/intelligence/gaps returns gap records."""
    org = make_org()
    test_db.add(org)

    gap = PortfolioGap(
        organization_id=org.id,
        problem_description="Niche barcode hardware sync problem",
        volume=5,
        opportunity_score=0.7,
        portfolio_coverage_score=0.0,
    )
    test_db.add(gap)
    await test_db.commit()

    token = create_access_token(
        user_id=str(uuid.uuid4()),
        organization_id=org.id,
        role="admin",
        permissions=["*"],
    )
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/intelligence/gaps", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["problem_description"] == "Niche barcode hardware sync problem"
