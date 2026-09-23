"""
apps/api/models/__init__.py

Exports all domain models for easy discovery by Alembic migrations and FastAPI routers.
"""

from core.database import Base
from .organization import Organization, User, Role, AuditLog
from .mission import Mission, MissionGoal, MissionRun
from .product import (
    Product, ProductBrain, ProductFeature, ProductProblem,
    ProductRelationship
)
from .worker import (
    WorkerType, Worker, WorkerRun, WorkerTask, WorkerAttempt,
    WorkerMessage, WorkerHeartbeat, WorkerMetric
)
from .event_journal import EventJournal
from .source import (
    Source, SourceConnection, SourceCursor, SourceHealth, CrawlFrontierItem
)
from .document import FetchedResource, Document, DocumentVersion
from .intelligence import (
    Entity, EntityAlias, Relationship, Signal, PortfolioMatch,
    PortfolioGap, CompetitorProfile, CompetitorEvent
)
from .research import (
    Investigation, InvestigationQuestion, Claim, Evidence,
    Verification, Contradiction
)
from .lead import (
    Conversation, Comment, Lead, Action, Approval, Outcome
)
from .learning import (
    LearningEvent, Feedback, SourceReliability
)

__all__ = [
    "Base",
    "Organization", "User", "Role", "AuditLog",
    "Mission", "MissionGoal", "MissionRun",
    "Product", "ProductBrain", "ProductFeature", "ProductProblem", "ProductRelationship",
    "WorkerType", "Worker", "WorkerRun", "WorkerTask", "WorkerAttempt", "WorkerMessage", "WorkerHeartbeat", "WorkerMetric",
    "EventJournal",
    "Source", "SourceConnection", "SourceCursor", "SourceHealth", "CrawlFrontierItem",
    "FetchedResource", "Document", "DocumentVersion",
    "Entity", "EntityAlias", "Relationship", "Signal", "PortfolioMatch", "PortfolioGap", "CompetitorProfile", "CompetitorEvent",
    "Investigation", "InvestigationQuestion", "Claim", "Evidence", "Verification", "Contradiction",
    "Conversation", "Comment", "Lead", "Action", "Approval", "Outcome",
    "LearningEvent", "Feedback", "SourceReliability"
]
