"""Cost and Pipeline data providers - Mock and Live."""

import os
import logging

logger = logging.getLogger(__name__)

# ============================================
# COST PROVIDERS
# ============================================
_cost_provider_instance = None


def is_live_mode() -> bool:
    """Check if live Azure mode is enabled."""
    return os.getenv("USE_LIVE_DATA", "false").lower() == "true"


def get_cost_provider():
    """Get the appropriate cost provider."""
    global _cost_provider_instance
    
    if _cost_provider_instance is not None:
        return _cost_provider_instance
    
    if is_live_mode():
        try:
            from .azure_cost_provider import AzureCostDataProvider
            provider = AzureCostDataProvider()
            if provider.is_available():
                logger.info("✅ Using LIVE Azure Cost Management API")
                _cost_provider_instance = provider
                return _cost_provider_instance
            else:
                logger.warning("⚠️ Azure not available, using mock data")
        except ImportError as e:
            logger.warning(f"⚠️ Azure SDK error: {e}")
    
    from .mock_cost_provider import MockCostDataProvider
    logger.info("🟡 Using MOCK cost data provider")
    _cost_provider_instance = MockCostDataProvider()
    return _cost_provider_instance


def reset_provider():
    """Reset cost provider (for testing)."""
    global _cost_provider_instance
    _cost_provider_instance = None


# ============================================
# PIPELINE PROVIDERS
# ============================================
_pipeline_provider_instance = None


def is_pipeline_live_mode() -> bool:
    """Check if live GitLab mode is enabled."""
    return os.getenv("USE_LIVE_DATA", "false").lower() == "true"


def get_pipeline_provider():
    """Get the appropriate pipeline provider."""
    global _pipeline_provider_instance
    
    if _pipeline_provider_instance is not None:
        return _pipeline_provider_instance
    
    if is_pipeline_live_mode():
        try:
            from .gitlab_pipeline_provider import GitLabPipelineProvider
            provider = GitLabPipelineProvider()
            if provider.is_available():
                logger.info("✅ Using LIVE GitLab Pipeline API")
                _pipeline_provider_instance = provider
                return _pipeline_provider_instance
            else:
                logger.warning("⚠️ GitLab not available, using mock data")
        except ImportError as e:
            logger.warning(f"⚠️ GitLab provider error: {e}")
    
    from .mock_pipeline_provider import MockPipelineDataProvider
    logger.info("🟡 Using MOCK pipeline data provider")
    _pipeline_provider_instance = MockPipelineDataProvider()
    return _pipeline_provider_instance


def reset_pipeline_provider():
    """Reset pipeline provider (for testing)."""
    global _pipeline_provider_instance
    _pipeline_provider_instance = None


__all__ = [
    # Cost providers
    "get_cost_provider", 
    "is_live_mode", 
    "reset_provider",
    # Pipeline providers
    "get_pipeline_provider",
    "is_pipeline_live_mode",
    "reset_pipeline_provider"
]
