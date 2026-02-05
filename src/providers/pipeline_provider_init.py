"""Pipeline data providers - Mock and GitLab."""

import os
import logging

logger = logging.getLogger(__name__)

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
    """Reset provider (for testing)."""
    global _pipeline_provider_instance
    _pipeline_provider_instance = None


__all__ = ["get_pipeline_provider", "is_pipeline_live_mode", "reset_pipeline_provider"]