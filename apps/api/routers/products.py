"""
apps/api/routers/products.py

REST API endpoints for Multi-Product Portfolio and ProductBrain management.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from core.database import get_db
from core.rbac import TenantContext, get_tenant_context, require_permission
from models import Product, ProductBrain, ProductRelationship

router = APIRouter(prefix="/api/products", tags=["Products"])

class ProductCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    slug: str = Field(min_length=2, max_length=100)
    category: str = "SaaS"
    description: str
    website: Optional[str] = None
    icp: Optional[str] = ""
    problems_solved: List[str] = Field(default_factory=list)
    problems_not_solved: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)

@router.get("")
async def list_products(
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns all products in the portfolio with brain summary.
    """
    stmt = (
        select(Product)
        .options(selectinload(Product.brain))
        .where(Product.organization_id == ctx.organization_id)
        .order_by(Product.name)
    )
    result = await db.execute(stmt)
    products = result.scalars().all()

    return [
        {
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "category": p.category,
            "description": p.description,
            "website": p.website,
            "status": p.status,
            "brain": {
                "icp": p.brain.icp if p.brain else "",
                "problems_solved_count": len(p.brain.problems_solved) if p.brain else 0,
                "problems_not_solved_count": len(p.brain.problems_not_solved) if p.brain else 0,
                "keywords": p.brain.keywords if p.brain else [],
                "pricing": p.brain.pricing if p.brain else {}
            } if p.brain else None
        }
        for p in products
    ]

@router.get("/{product_id}")
async def get_product_detail(
    product_id: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns full details including complete ProductBrain.
    """
    stmt = (
        select(Product)
        .options(selectinload(Product.brain))
        .where(Product.id == product_id, Product.organization_id == ctx.organization_id)
    )
    res = await db.execute(stmt)
    product = res.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    b = product.brain
    return {
        "id": product.id,
        "name": product.name,
        "slug": product.slug,
        "category": product.category,
        "description": product.description,
        "website": product.website,
        "status": product.status,
        "brain": {
            "icp": b.icp if b else "",
            "personas": b.personas if b else [],
            "industries": b.industries if b else [],
            "problems_solved": b.problems_solved if b else [],
            "problems_not_solved": b.problems_not_solved if b else [],
            "product_boundaries": b.product_boundaries if b else "",
            "keywords": b.keywords if b else [],
            "semantic_concepts": b.semantic_concepts if b else [],
            "customer_language": b.customer_language if b else [],
            "negative_keywords": b.negative_keywords if b else [],
            "competitors": b.competitors if b else [],
            "alternatives": b.alternatives if b else [],
            "proof_points": b.proof_points if b else [],
            "pricing": b.pricing if b else {},
            "approved_claims": b.approved_claims if b else [],
            "forbidden_claims": b.forbidden_claims if b else [],
        } if b else None
    }

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_product(
    req: ProductCreateRequest,
    ctx: TenantContext = Depends(require_permission("product:write")),
    db: AsyncSession = Depends(get_db)
):
    """
    Adds a new product to the portfolio dynamically.
    No new worker or crawler code required.
    """
    product = Product(
        organization_id=ctx.organization_id,
        name=req.name,
        slug=req.slug,
        category=req.category,
        description=req.description,
        website=req.website,
        status="active"
    )
    db.add(product)
    await db.flush()

    brain = ProductBrain(
        product_id=product.id,
        icp=req.icp or "",
        problems_solved=req.problems_solved,
        problems_not_solved=req.problems_not_solved,
        keywords=req.keywords
    )
    db.add(brain)
    await db.commit()

    return {"id": product.id, "name": product.name, "status": "created"}
