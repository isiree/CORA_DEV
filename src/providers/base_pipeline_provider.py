"""Base class for pipeline data providers."""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime


class PipelineDataProvider(ABC):
    """Abstract base class for pipeline data providers."""
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider name (mock/gitlab)."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available."""
        pass
    
    @abstractmethod
    def get_team_keys(self) -> List[str]:
        """Get list of available team keys."""
        pass
    
    @abstractmethod
    def get_pipelines(self, team_name: str, days: int = 7) -> dict:
        """Get recent pipelines for a team."""
        pass
    
    @abstractmethod
    def get_pipeline_details(self, pipeline_id: int) -> dict:
        """Get details of a specific pipeline."""
        pass
    
    @abstractmethod
    def get_job_logs(self, pipeline_id: int, job_name: str) -> dict:
        """Get logs for a specific job."""
        pass
    
    @abstractmethod
    def get_infrastructure_changes(self, team_name: str, days: int = 7) -> dict:
        """Get infrastructure changes from pipelines."""
        pass
    
    @abstractmethod
    def trigger_pipeline(self, team_name: str, action: str, variables: dict = None) -> dict:
        """Trigger a new pipeline with specified action."""
        pass