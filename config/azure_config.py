"""Azure configuration for IMRAG."""

import os
from dataclasses import dataclass
from typing import Optional
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


@dataclass
class TeamConfig:
    """Configuration for a team."""
    name: str
    display_name: str
    lead: str
    lead_email: str
    resource_group: str
    monthly_budget: float


class AzureConfig:
    """Azure configuration manager."""
    
    def __init__(self):
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID", "")
        self.use_live_data = os.getenv("USE_LIVE_AZURE_DATA", "false").lower() == "true"
        
        # Team configurations (maps to Azure resource groups)
        self._teams = {
            "release-team": TeamConfig(
                name="release-team",
                display_name="Release Team",
                lead="Alex Johnson",
                lead_email="alex.johnson@abc-company.com",
                resource_group="rg-release-team",
                monthly_budget=50.0
            ),
            "ci-team": TeamConfig(
                name="ci-team",
                display_name="CI Team",
                lead="James Wilson",
                lead_email="james.wilson@abc-company.com",
                resource_group="rg-ci-team",
                monthly_budget=30.0
            ),
            "cloudops-team": TeamConfig(
                name="cloudops-team",
                display_name="CloudOps Team",
                lead="David Brown",
                lead_email="david.brown@abc-company.com",
                resource_group="rg-cloudops-team",
                monthly_budget=20.0
            )
        }
    
    def get_team(self, team_name: str) -> Optional[TeamConfig]:
        """Get team configuration."""
        normalized = team_name.lower().replace(" ", "-").replace("_", "-")
        return self._teams.get(normalized)
    
    def get_all_teams(self) -> list[TeamConfig]:
        """Get all team configurations."""
        return list(self._teams.values())
    
    def has_subscription(self) -> bool:
        """Check if subscription is configured."""
        return bool(self.subscription_id)


@lru_cache()
def get_azure_config() -> AzureConfig:
    """Get global config instance."""
    return AzureConfig()