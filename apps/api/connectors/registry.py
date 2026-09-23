"""
apps/api/connectors/registry.py

ConnectorRegistry — maps source platform name → connector class.
Adding a new source = register it here. Zero changes to intelligence logic.
"""

from __future__ import annotations

from typing import Dict, Optional, Type
import structlog

from .base import BaseSourceConnector

logger = structlog.get_logger(__name__)

_REGISTRY: Dict[str, Type[BaseSourceConnector]] = {}


def register(platform: str):
    """Decorator to register a connector class under a platform name."""
    def decorator(cls: Type[BaseSourceConnector]) -> Type[BaseSourceConnector]:
        _REGISTRY[platform.lower()] = cls
        logger.debug("connector_registered", platform=platform)
        return cls
    return decorator


def get_connector(platform: str) -> Optional[Type[BaseSourceConnector]]:
    return _REGISTRY.get(platform.lower())


def get_all_platforms() -> list[str]:
    return list(_REGISTRY.keys())


def build_connector(platform: str) -> Optional[BaseSourceConnector]:
    """Instantiate a connector by platform name."""
    cls = get_connector(platform)
    if cls is None:
        logger.warning("connector_not_found", platform=platform)
        return None
    return cls()


# Auto-import connectors to trigger registration
def _auto_import() -> None:
    # youtube is first — primary discovery source
    from . import youtube, website, rss, search, reddit, news  # noqa: F401


_auto_import()
