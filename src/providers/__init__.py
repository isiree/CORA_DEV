"""
Cloud cost and pipeline data providers.

Supports both live API calls and mock data for demos.
The USE_LIVE_DATA environment variable controls which mode is used.
"""

import os
import logging

# Import base classes
from .base_provider import CostDataProvider
from .base_pipeline_provider import PipelineDataProvider

# Import providers with correct class names
from .azure_cost_provider import AzureCostDataProvider
from .mock_cost_provider import MockCostDataProvider
from .gitlab_pipeline_provider import GitLabPipelineProvider
from .mock_pipeline_provider import MockPipelineDataProvider

logger = logging.getLogger(__name__)

__all__ = [
    # Base classes
    "CostDataProvider",
    "PipelineDataProvider",
    # Cost providers
    "AzureCostDataProvider",
    "MockCostDataProvider",
    # Pipeline providers
    "GitLabPipelineProvider",
    "MockPipelineDataProvider",
    # Helper functions
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
        AzureCostDataProvider if live mode enabled and configured,
        MockCostDataProvider otherwise.
    """
    if is_azure_live_mode():
        return AzureCostDataProvider()
    return MockCostDataProvider()


def get_pipeline_provider():
    """
    Get the appropriate pipeline provider based on configuration.
    
    Returns:
        GitLabPipelineProvider if live mode enabled and configured,
        MockPipelineDataProvider otherwise.
    """
    if is_gitlab_live_mode():
        return GitLabPipelineProvider()
    return MockPipelineDataProvider()
