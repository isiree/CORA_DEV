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


def _is_mock_mode() -> bool:
    """Check if system should use mock data mode."""
    return not is_live_mode()


def is_azure_live_mode() -> bool:
    """
    Check if Azure Cost Management should use live API data.
    
    For Azure CLI authentication (student subscriptions), only requires:
        - USE_LIVE_DATA=true
        - AZURE_SUBSCRIPTION_ID
    
    For SPN authentication, also requires:
        - AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET
    
    Returns:
        True if live Azure mode is enabled and configured.
    """
    if not is_live_mode():
        return False
    
    # Minimum requirement: subscription ID
    if not os.getenv("AZURE_SUBSCRIPTION_ID"):
        return False
    
    # Check if using CLI auth or SPN auth
    has_spn_creds = all([
        os.getenv("AZURE_TENANT_ID"),
        os.getenv("AZURE_CLIENT_ID"),
        os.getenv("AZURE_CLIENT_SECRET")
    ])
    
    use_cli_auth = os.getenv("AZURE_USE_CLI_AUTH", "true").lower() == "true"
    
    # Either SPN creds OR CLI auth enabled
    return has_spn_creds or use_cli_auth


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


_cost_provider_instance = None
_pipeline_provider_instance = None

def get_cost_provider():
    """
    Get the appropriate cost provider based on configuration.
    
    Returns:
        AzureCostDataProvider if live mode enabled and configured,
        MockCostDataProvider otherwise.
    """
    global _cost_provider_instance
    
    if _cost_provider_instance is not None:
        return _cost_provider_instance

    if _is_mock_mode():
        logger.info("🟡 Using MOCK cost data provider")
        _cost_provider_instance = MockCostDataProvider()
        return _cost_provider_instance

    if not is_azure_live_mode():
        logger.warning("⚠️ Azure live mode not fully configured, falling back to mock")
        _cost_provider_instance = MockCostDataProvider()
        return _cost_provider_instance

    try:
        provider = AzureCostDataProvider()
        # only check live provider availability in live mode
        if provider.is_available():
            logger.info("✅ Using LIVE Azure Cost API")
            _cost_provider_instance = provider
        else:
            logger.warning("⚠️ Azure provider not available, falling back to mock")
            _cost_provider_instance = MockCostDataProvider()
    except Exception as e:
        logger.warning(f"⚠️ Azure provider error: {e}, falling back to mock")
        _cost_provider_instance = MockCostDataProvider()

    return _cost_provider_instance


def get_pipeline_provider():
    """
    Get the appropriate pipeline provider based on configuration.
    
    Returns:
        GitLabPipelineProvider if live mode enabled and configured,
        MockPipelineDataProvider otherwise.
    """
    global _pipeline_provider_instance

    if _pipeline_provider_instance is not None:
        return _pipeline_provider_instance

    if not is_gitlab_live_mode():
        _pipeline_provider_instance = MockPipelineDataProvider()
        return _pipeline_provider_instance

    try:
        provider = GitLabPipelineProvider()
        if provider.is_available():
            logger.info("✅ Using LIVE GitLab Pipeline API")
            _pipeline_provider_instance = provider
        else:
            logger.warning("⚠️ GitLab provider not available, falling back to mock")
            _pipeline_provider_instance = MockPipelineDataProvider()
    except Exception as e:
        logger.warning(f"⚠️ GitLab provider error: {e}, falling back to mock")
        _pipeline_provider_instance = MockPipelineDataProvider()

    return _pipeline_provider_instance
