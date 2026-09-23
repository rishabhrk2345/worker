"""Connector package — imports trigger @register() decorators."""
from .base import BaseSourceConnector, SearchResult, FetchResult, Comment, HealthStatus
from .registry import get_connector, build_connector, get_all_platforms
from .rate_limiter import get_rate_limit_manager
from .health_monitor import get_health_monitor
# Import connectors to fire their @register() decorators
from . import website, rss, search, reddit, news  # noqa: F401

__all__ = [
    "BaseSourceConnector", "SearchResult", "FetchResult", "Comment", "HealthStatus",
    "get_connector", "build_connector", "get_all_platforms",
    "get_rate_limit_manager", "get_health_monitor",
]
