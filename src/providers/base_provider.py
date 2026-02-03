"""Abstract base class for cost data providers."""

from abc import ABC, abstractmethod
from typing import List


class CostDataProvider(ABC):
    """Abstract base class for cost data providers."""
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider name ('mock' or 'azure')."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available."""
        pass
    
    @abstractmethod
    def get_team_keys(self) -> List[str]:
        """Return list of valid team keys."""
        pass
    
    @abstractmethod
    def get_team_spending(self, team_name: str, days: int = 30) -> dict:
        """Get spending data for a team."""
        pass
    
    @abstractmethod
    def get_all_teams_summary(self) -> dict:
        """Get summary of all teams."""
        pass
    
    @abstractmethod
    def get_subscription_costs(self, subscription_id: str, days: int = 7) -> dict:
        """Get subscription costs."""
        pass