"""
Cost API Tool - Azure Cost Management API integration.

For demo purposes, this tool uses mock data that simulates real Azure Cost Management API responses.
In production, replace mock data with actual Azure SDK calls.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool
from dotenv import load_dotenv

from ..utils.cache_manager import get_cache

load_dotenv()


# Mock data for demo - simulates ABC Company's cloud spending
MOCK_TEAM_DATA = {
    "release-team": {
        "team_name": "Release Team",
        "lead": "Alex Johnson",
        "members": 4,
        "budget_monthly": 2400,
        "subscriptions": ["sub-2401-rel-prod", "sub-2401-rel-stage", "sub-2401-rel-tools"],
        "current_spend": 2650,  # Over budget!
        "forecast_month_end": 2850,
        "cost_breakdown": {
            "compute": 1500,
            "storage": 450,
            "networking": 350,
            "other": 350
        },
        "daily_spend_last_7_days": [320, 380, 410, 395, 420, 365, 360],
        "anomalies": ["Spike on day 3: New VM deployment detected"]
    },
    "ci-team": {
        "team_name": "CI Team",
        "lead": "James Wilson",
        "members": 3,
        "budget_monthly": 2400,
        "subscriptions": ["sub-2401-ci-build", "sub-2401-ci-test", "sub-2401-ci-tools"],
        "current_spend": 1850,
        "forecast_month_end": 2200,
        "cost_breakdown": {
            "compute": 1200,
            "storage": 300,
            "networking": 200,
            "other": 150
        },
        "daily_spend_last_7_days": [260, 270, 265, 280, 275, 260, 240],
        "anomalies": []
    },
    "cloudops-team": {
        "team_name": "CloudOps Team",
        "lead": "David Brown",
        "members": 4,
        "budget_monthly": 3600,
        "subscriptions": ["sub-2401-ops-prod", "sub-2401-ops-dr", "sub-2401-ops-infra", "sub-2401-ops-dev"],
        "current_spend": 3200,
        "forecast_month_end": 3800,
        "cost_breakdown": {
            "compute": 2000,
            "storage": 600,
            "networking": 400,
            "other": 200
        },
        "daily_spend_last_7_days": [450, 460, 480, 470, 455, 445, 440],
        "anomalies": ["DR failover test on day 3 caused temporary spike"]
    }
}


class CostAPITool:
    """
    Tool for retrieving cloud cost data from Azure Cost Management API.
    Uses mock data for demo, but structured to easily swap in real API calls.
    """
    
    def __init__(self):
        self.cache = get_cache()
        self.cache_ttl = 300  # 5 minutes
        
        # In production, initialize Azure SDK client here
        # self.azure_client = CostManagementClient(credential, subscription_id)
    
    def _normalize_team_name(self, team_name: str) -> str:
        """Normalize team name for lookup."""
        return team_name.lower().replace(" ", "-").replace("_", "-")
    
    def get_team_spending(self, team_name: str, days: int = 30) -> dict:
        """
        Get spending data for a specific team.
        
        Args:
            team_name: Name of the team (e.g., "release-team", "Release Team")
            days: Number of days to look back
        
        Returns:
            Dictionary with spending data
        """
        # Check cache
        cached = self.cache.get("cost_api", team_name=team_name, days=days)
        if cached:
            return cached
        
        normalized_name = self._normalize_team_name(team_name)
        
        if normalized_name not in MOCK_TEAM_DATA:
            return {
                "success": False,
                "error": f"Team '{team_name}' not found. Available teams: Release Team, CI Team, CloudOps Team"
            }
        
        data = MOCK_TEAM_DATA[normalized_name]
        
        # Calculate budget status
        budget_used_pct = (data["current_spend"] / data["budget_monthly"]) * 100
        budget_status = "NORMAL"
        if budget_used_pct >= 110:
            budget_status = "CRITICAL - AUTO COST HOLD TRIGGERED"
        elif budget_used_pct >= 90:
            budget_status = "URGENT - ESCALATE TO COST COUNCIL"
        elif budget_used_pct >= 75:
            budget_status = "WARNING"
        elif budget_used_pct >= 50:
            budget_status = "INFORMATIONAL"
        
        result = {
            "success": True,
            "team_name": data["team_name"],
            "lead": data["lead"],
            "period": f"Last {days} days",
            "retrieved_at": datetime.now().isoformat(),
            "budget": {
                "monthly_budget": f"${data['budget_monthly']:,}",
                "current_spend": f"${data['current_spend']:,}",
                "forecast_month_end": f"${data['forecast_month_end']:,}",
                "budget_used_percentage": f"{budget_used_pct:.1f}%",
                "budget_status": budget_status
            },
            "subscriptions": data["subscriptions"],
            "cost_breakdown": {k: f"${v:,}" for k, v in data["cost_breakdown"].items()},
            "daily_trend": data["daily_spend_last_7_days"],
            "anomalies": data["anomalies"] if data["anomalies"] else ["No anomalies detected"]
        }
        
        # Cache result
        self.cache.set("cost_api", result, team_name=team_name, days=days)
        
        return result
    
    def get_all_teams_summary(self) -> dict:
        """Get summary of all teams' spending."""
        summary = {
            "success": True,
            "retrieved_at": datetime.now().isoformat(),
            "teams": []
        }
        
        total_budget = 0
        total_spend = 0
        
        for team_key, data in MOCK_TEAM_DATA.items():
            budget_pct = (data["current_spend"] / data["budget_monthly"]) * 100
            total_budget += data["budget_monthly"]
            total_spend += data["current_spend"]
            
            summary["teams"].append({
                "team": data["team_name"],
                "budget": f"${data['budget_monthly']:,}",
                "spend": f"${data['current_spend']:,}",
                "percentage": f"{budget_pct:.1f}%",
                "status": "⚠️ OVER" if budget_pct > 100 else "✅ OK"
            })
        
        summary["totals"] = {
            "total_budget": f"${total_budget:,}",
            "total_spend": f"${total_spend:,}",
            "overall_percentage": f"{(total_spend/total_budget)*100:.1f}%"
        }
        
        return summary
    
    def get_subscription_costs(self, subscription_id: str, days: int = 7) -> dict:
        """Get costs for a specific subscription."""
        # Find which team owns this subscription
        for team_key, data in MOCK_TEAM_DATA.items():
            if subscription_id in data["subscriptions"]:
                per_sub_cost = data["current_spend"] / len(data["subscriptions"])
                return {
                    "success": True,
                    "subscription_id": subscription_id,
                    "owning_team": data["team_name"],
                    "period": f"Last {days} days",
                    "total_cost": f"${per_sub_cost:.2f}",
                    "daily_average": f"${per_sub_cost/30:.2f}"
                }
        
        return {
            "success": False,
            "error": f"Subscription '{subscription_id}' not found"
        }


# Singleton instance
_cost_tool_instance: Optional[CostAPITool] = None


def get_cost_tool() -> CostAPITool:
    """Get or create global cost tool instance."""
    global _cost_tool_instance
    if _cost_tool_instance is None:
        _cost_tool_instance = CostAPITool()
    return _cost_tool_instance


@tool
def cost_api_tool(query: str) -> str:
    """
    Get real-time cloud cost data from Azure Cost Management API.
    
    Use this tool when you need:
    - Current spending for a team
    - Budget status and thresholds
    - Cost breakdown by resource type
    - Spending trends and anomalies
    - Subscription-level costs
    
    Args:
        query: Query about costs. Include team name if asking about specific team.
               Examples: "release team spending", "all teams summary", "subscription sub-2401-rel-prod costs"
    
    Returns:
        Cost data with budget status and breakdown
    """
    tool_instance = get_cost_tool()
    query_lower = query.lower()
    
    # Determine what data to fetch based on query
    if "all team" in query_lower or "summary" in query_lower or "overview" in query_lower:
        result = tool_instance.get_all_teams_summary()
        
        # Format for agent
        output = ["📊 ALL TEAMS COST SUMMARY", "=" * 40]
        for team in result["teams"]:
            output.append(f"{team['status']} {team['team']}: {team['spend']} / {team['budget']} ({team['percentage']})")
        output.append("-" * 40)
        output.append(f"TOTAL: {result['totals']['total_spend']} / {result['totals']['total_budget']} ({result['totals']['overall_percentage']})")
        return "\n".join(output)
    
    # Check for specific subscription
    if "sub-" in query_lower:
        # Extract subscription ID
        import re
        match = re.search(r'sub-[\w-]+', query_lower)
        if match:
            sub_id = match.group(0)
            result = tool_instance.get_subscription_costs(sub_id)
            if result["success"]:
                return f"Subscription {sub_id}: {result['total_cost']} (owned by {result['owning_team']})"
            return result["error"]
    
    # Check for team name
    for team_key in MOCK_TEAM_DATA.keys():
        team_variants = [team_key, team_key.replace("-", " "), team_key.replace("-", "_")]
        if any(v in query_lower for v in team_variants):
            result = tool_instance.get_team_spending(team_key)
            if not result["success"]:
                return result["error"]
            
            # Format response
            output = [
                f"💰 COST DATA: {result['team_name']}",
                f"Lead: {result['lead']}",
                f"Period: {result['period']}",
                "",
                "📊 BUDGET STATUS:",
                f"  Monthly Budget: {result['budget']['monthly_budget']}",
                f"  Current Spend: {result['budget']['current_spend']}",
                f"  Budget Used: {result['budget']['budget_used_percentage']}",
                f"  Status: {result['budget']['budget_status']}",
                f"  Forecast: {result['budget']['forecast_month_end']}",
                "",
                "📦 COST BREAKDOWN:",
            ]
            for resource, cost in result["cost_breakdown"].items():
                output.append(f"  {resource}: {cost}")
            
            output.append("")
            output.append("⚠️ ANOMALIES:")
            for anomaly in result["anomalies"]:
                output.append(f"  - {anomaly}")
            
            return "\n".join(output)
    
    # Default: return all teams summary
    return cost_api_tool.invoke("all teams summary")
