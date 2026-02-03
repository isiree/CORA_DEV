"""Mock data provider for development and testing."""

from datetime import datetime
from typing import List
from .base_provider import CostDataProvider


MOCK_TEAMS = {
    "release-team": {
        "team_name": "Release Team",
        "lead": "Alex Johnson",
        "lead_email": "alex.johnson@abc-company.com",
        "resource_group": "rg-release-team",
        "budget_monthly": 2400,
        "subscriptions": ["sub-2401-rel-prod", "sub-2401-rel-stage"],
        "current_spend": 2650,
        "forecast_month_end": 2850,
        "cost_breakdown": {"compute": 1500, "storage": 450, "networking": 350, "other": 350},
        "daily_spend_last_7_days": [320, 380, 410, 395, 420, 365, 360],
        "anomalies": ["Spike on day 3: New VM deployment detected"]
    },
    "ci-team": {
        "team_name": "CI Team",
        "lead": "James Wilson",
        "lead_email": "james.wilson@abc-company.com",
        "resource_group": "rg-ci-team",
        "budget_monthly": 2400,
        "subscriptions": ["sub-2401-ci-build", "sub-2401-ci-test"],
        "current_spend": 1850,
        "forecast_month_end": 2200,
        "cost_breakdown": {"compute": 1200, "storage": 300, "networking": 200, "other": 150},
        "daily_spend_last_7_days": [260, 270, 265, 280, 275, 260, 240],
        "anomalies": []
    },
    "cloudops-team": {
        "team_name": "CloudOps Team",
        "lead": "David Brown",
        "lead_email": "david.brown@abc-company.com",
        "resource_group": "rg-cloudops-team",
        "budget_monthly": 3600,
        "subscriptions": ["sub-2401-ops-prod", "sub-2401-ops-dr"],
        "current_spend": 3200,
        "forecast_month_end": 3800,
        "cost_breakdown": {"compute": 2000, "storage": 600, "networking": 400, "other": 200},
        "daily_spend_last_7_days": [450, 460, 480, 470, 455, 445, 440],
        "anomalies": ["DR failover test on day 3 caused temporary spike"]
    }
}


class MockCostDataProvider(CostDataProvider):
    """Mock implementation of cost data provider."""
    
    def __init__(self):
        self.data = MOCK_TEAMS
    
    @property
    def provider_name(self) -> str:
        return "mock"
    
    def is_available(self) -> bool:
        return True
    
    def get_team_keys(self) -> List[str]:
        return list(self.data.keys())
    
    def _normalize_team_name(self, team_name: str) -> str:
        return team_name.lower().replace(" ", "-").replace("_", "-")
    
    def _get_budget_status(self, pct: float) -> str:
        if pct >= 110:
            return "CRITICAL - AUTO COST HOLD TRIGGERED"
        elif pct >= 90:
            return "URGENT - ESCALATE TO COST COUNCIL"
        elif pct >= 75:
            return "WARNING"
        elif pct >= 50:
            return "INFORMATIONAL"
        return "NORMAL"
    
    def get_team_spending(self, team_name: str, days: int = 30) -> dict:
        normalized = self._normalize_team_name(team_name)
        
        if normalized not in self.data:
            return {
                "success": False,
                "error": f"Team '{team_name}' not found. Available: {', '.join(self.data.keys())}"
            }
        
        team = self.data[normalized]
        budget_pct = (team["current_spend"] / team["budget_monthly"]) * 100
        
        return {
            "success": True,
            "team_name": team["team_name"],
            "lead": team["lead"],
            "period": f"Last {days} days",
            "retrieved_at": datetime.now().isoformat(),
            "data_source": "mock",
            "budget": {
                "monthly_budget": f"${team['budget_monthly']:,}",
                "current_spend": f"${team['current_spend']:,}",
                "forecast_month_end": f"${team['forecast_month_end']:,}",
                "budget_used_percentage": f"{budget_pct:.1f}%",
                "budget_status": self._get_budget_status(budget_pct)
            },
            "subscriptions": team["subscriptions"],
            "cost_breakdown": {k: f"${v:,}" for k, v in team["cost_breakdown"].items()},
            "daily_trend": team["daily_spend_last_7_days"],
            "anomalies": team["anomalies"] if team["anomalies"] else ["No anomalies detected"]
        }
    
    def get_all_teams_summary(self) -> dict:
        teams = []
        total_budget = 0
        total_spend = 0
        
        for team_key, team in self.data.items():
            budget_pct = (team["current_spend"] / team["budget_monthly"]) * 100
            total_budget += team["budget_monthly"]
            total_spend += team["current_spend"]
            
            teams.append({
                "team": team["team_name"],
                "budget": f"${team['budget_monthly']:,}",
                "spend": f"${team['current_spend']:,}",
                "percentage": f"{budget_pct:.1f}%",
                "status": "⚠️ OVER" if budget_pct > 100 else "✅ OK"
            })
        
        return {
            "success": True,
            "retrieved_at": datetime.now().isoformat(),
            "data_source": "mock",
            "teams": teams,
            "totals": {
                "total_budget": f"${total_budget:,}",
                "total_spend": f"${total_spend:,}",
                "overall_percentage": f"{(total_spend/total_budget)*100:.1f}%"
            }
        }
    
    def get_subscription_costs(self, subscription_id: str, days: int = 7) -> dict:
        for team_key, team in self.data.items():
            if subscription_id in team["subscriptions"]:
                per_sub_cost = team["current_spend"] / len(team["subscriptions"])
                return {
                    "success": True,
                    "subscription_id": subscription_id,
                    "owning_team": team["team_name"],
                    "period": f"Last {days} days",
                    "total_cost": f"${per_sub_cost:.2f}",
                    "daily_average": f"${per_sub_cost/30:.2f}",
                    "data_source": "mock"
                }
        
        return {"success": False, "error": f"Subscription '{subscription_id}' not found"}