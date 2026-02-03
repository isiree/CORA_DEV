"""Cost data providers - Mock and Azure."""

import os
import logging

logger = logging.getLogger(__name__)

_provider_instance = None


def is_live_mode() -> bool:
    """Check if live Azure mode is enabled."""
    return os.getenv("USE_LIVE_DATA", "false").lower() == "true"


def get_cost_provider():
    """Get the appropriate cost provider."""
    global _provider_instance
    
    if _provider_instance is not None:
        return _provider_instance
    
    if is_live_mode():
        try:
            from .azure_cost_provider import AzureCostDataProvider
            provider = AzureCostDataProvider()
            if provider.is_available():
                logger.info("✅ Using LIVE Azure Cost Management API")
                _provider_instance = provider
                return _provider_instance
            else:
                logger.warning("⚠️ Azure not available, using mock data")
        except ImportError as e:
            logger.warning(f"⚠️ Azure SDK error: {e}")
    
    from .mock_cost_provider import MockCostDataProvider
    logger.info("🟡 Using MOCK data provider")
    _provider_instance = MockCostDataProvider()
    return _provider_instance


def reset_provider():
    """Reset provider (for testing)."""
    global _provider_instance
    _provider_instance = None


__all__ = ["get_cost_provider", "is_live_mode", "reset_provider"]
