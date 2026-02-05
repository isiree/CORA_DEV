"""
Cloud cost and pipeline data providers.

Supports both live API calls and mock data for demos.
The USE_LIVE_DATA environment variable controls which mode is used.
"""

import os
import logging

# Import providers
from .azure_cost_provider import AzureCostProvider
from .mock_cost_provider import MockCostProvider
from .gitlab_pipeline_provider import GitLabPipelineProvider
from .mock_pipeline_provider import MockPipelineProvider

logger = logging.getLogger(__name__)

__all__ = [
    "AzureCostProvider",
    "MockCostProvider",
    "GitLabPipelineProvider",
    "MockPipelineProvider",
    "is_live_mode",
    "is_azure_live_mode",
    "is_gitlab_live_mode",
    "get_cost_provider",
    "get_pipeline_provider"
]


def is_live_mode() -> bool:
    """
    Check if system should use live API data.
    
    Returns:
        True if USE_LIVE_DATA=true in environment, False otherwise.
    """
    return os.getenv("USE_LIVE_DATA", "false").lower() == "true"


def is_azure_live_mode() -> bool:
    """
    Check if Azure Cost Management should use live API data.
    
    Requires:
        - USE_LIVE_DATA=true
        - All Azure credentials configured
    
    Returns:
        True if live Azure mode is enabled and configured.
    """
    if not is_live_mode():
        return False
    
    required_vars = [
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_TENANT_ID", 
        "AZURE_CLIENT_ID",
        "AZURE_CLIENT_SECRET"
    ]
    return all(os.getenv(var) for var in required_vars)


def is_gitlab_live_mode() -> bool:
    """
    Check if GitLab CI/CD should use live API data.
    
    Requires:
        - USE_LIVE_DATA=true
        - GitLab token and project ID configured
    
    Returns:
        True if live GitLab mode is enabled and configured.
    """
    if not is_live_mode():
        return False
    
    required_vars = [
        "GITLAB_TOKEN",
        "GITLAB_PROJECT_ID"
    ]
    return all(os.getenv(var) for var in required_vars)


def get_cost_provider():
    """
    Get the appropriate cost provider based on configuration.
    
    Returns:
        AzureCostProvider if live mode enabled and configured,
        MockCostProvider otherwise.
    """
    if is_azure_live_mode():
        return AzureCostProvider()
    return MockCostProvider()


def get_pipeline_provider():
    """
    Get the appropriate pipeline provider based on configuration.
    
    Returns:
        GitLabPipelineProvider if live mode enabled and configured,
        MockPipelineProvider otherwise.
    """
    if is_gitlab_live_mode():
        return GitLabPipelineProvider()
    return MockPipelineProvider()
