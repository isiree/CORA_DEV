"""
Cost API Tool - Azure Cost Management API integration.

This tool handles:
1. Cost/spending queries (from Azure Cost Management API)
2. Resource discovery queries (from Azure Resource Manager API)
"""

import os
import re
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool
from dotenv import load_dotenv

from ..utils.cache_manager import get_cache
from ..providers import get_cost_provider, is_live_mode

load_dotenv()


class CostAPITool:
    """
    Tool for retrieving cloud cost data and resource information from Azure.
    """
    
    def __init__(self):
        self.cache = get_cache()
        self.cache_ttl = int(os.getenv("COST_CACHE_TTL", "300"))
        self._provider = None

    @property
    def provider(self):
        """Lazy load the provider."""
        if self._provider is None:
            self._provider = get_cost_provider()
        return self._provider
    
    def _normalize_team_name(self, team_name: str) -> str:
        """Normalize team name for lookup."""
        return team_name.lower().replace(" ", "-").replace("_", "-")
    
    def get_team_spending(self, team_name: str, days: int = 30) -> dict:
        """Get spending data for a specific team."""
        cached = self.cache.get("cost_api", team_name=team_name, days=days)
        if cached:
            return cached
        
        result = self.provider.get_team_spending(team_name, days)
        self.cache.set("cost_api", result, team_name=team_name, days=days)
        return result
    
    def get_all_teams_summary(self) -> dict:
        """Get summary of all teams' spending."""
        return self.provider.get_all_teams_summary()
    
    def get_subscription_costs(self, subscription_id: str, days: int = 7) -> dict:
        """Get costs for a specific subscription."""
        return self.provider.get_subscription_costs(subscription_id, days)
    
    # ============================================
    # RESOURCE DISCOVERY METHODS (NEW)
    # ============================================
    
    def get_team_resources(self, team_name: str) -> dict:
        """Get all resources for a team."""
        if hasattr(self.provider, 'get_team_resources'):
            return self.provider.get_team_resources(team_name)
        return {"success": False, "error": "Resource discovery not available in mock mode"}
    
    def get_all_resources(self) -> dict:
        """Get all resources in the resource group."""
        if hasattr(self.provider, 'get_all_resources'):
            return self.provider.get_all_resources()
        return {"success": False, "error": "Resource discovery not available in mock mode"}
    
    def get_storage_accounts(self, team_name: str = None) -> dict:
        """Get storage accounts, optionally filtered by team."""
        if hasattr(self.provider, 'get_storage_accounts'):
            return self.provider.get_storage_accounts(team_name)
        return {"success": False, "error": "Resource discovery not available in mock mode"}
    
    def get_container_instances(self, team_name: str = None) -> dict:
        """Get container instances, optionally filtered by team."""
        if hasattr(self.provider, 'get_container_instances'):
            return self.provider.get_container_instances(team_name)
        return {"success": False, "error": "Resource discovery not available in mock mode"}


# Singleton instance
_cost_tool_instance: Optional[CostAPITool] = None


def get_cost_tool() -> CostAPITool:
    """Get or create global cost tool instance."""
    global _cost_tool_instance
    if _cost_tool_instance is None:
        _cost_tool_instance = CostAPITool()
    return _cost_tool_instance


def _extract_team_from_query(query_lower: str, provider) -> Optional[str]:
    """Extract team name from query."""
    for team_key in provider.get_team_keys():
        team_variants = [team_key, team_key.replace("-", " "), team_key.replace("-", "_")]
        if any(v in query_lower for v in team_variants):
            return team_key
    return None


def _is_resource_query(query_lower: str) -> bool:
    """Check if query is asking about resources (not costs)."""
    resource_keywords = [
        "storage", "container", "resource", "deployed", "infrastructure",
        "what resources", "list resources", "show resources", "which resources",
        "vm", "virtual machine", "function", "key vault", "app service",
        "have", "has", "does", "do they have", "are there"
    ]
    cost_keywords = [
        "cost", "spend", "spending", "budget", "money", "expense", "bill",
        "charge", "price", "paid", "paying"
    ]
    
    has_resource_keyword = any(kw in query_lower for kw in resource_keywords)
    has_cost_keyword = any(kw in query_lower for kw in cost_keywords)
    
    # If asking about resources but not explicitly about costs
    return has_resource_keyword and not has_cost_keyword


def _format_resources_response(result: dict, resource_type: str = None) -> str:
    """Format resource discovery response."""
    if not result["success"]:
        return f"❌ Error: {result['error']}"
    
    output = []
    
    if "storage_accounts" in result:
        # Storage accounts response
        team_info = f" for {result['team']}" if result.get('team') else ""
        output.append(f"🗄️ STORAGE ACCOUNTS{team_info}")
        output.append("=" * 40)
        
        if result["storage_accounts"]:
            for acc in result["storage_accounts"]:
                output.append(f"  📦 {acc['name']}")
                output.append(f"     Location: {acc['location']}")
                if acc.get('team'):
                    output.append(f"     Team: {acc['team']}")
                if acc.get('tags'):
                    tags_str = ", ".join(f"{k}={v}" for k, v in acc['tags'].items() if k != 'team')
                    if tags_str:
                        output.append(f"     Tags: {tags_str}")
            output.append("")
            output.append(f"Total: {result['count']} storage account(s)")
        else:
            output.append("  No storage accounts found")
    
    elif "container_instances" in result:
        # Container instances response
        team_info = f" for {result['team']}" if result.get('team') else ""
        output.append(f"🐳 CONTAINER INSTANCES{team_info}")
        output.append("=" * 40)
        
        if result["container_instances"]:
            for container in result["container_instances"]:
                output.append(f"  📦 {container['name']}")
                output.append(f"     Location: {container['location']}")
        else:
            output.append("  No container instances found")
    
    elif "grouped" in result:
        # All resources response (grouped by type)
        output.append(f"📦 RESOURCES: {result.get('team', 'All Teams')}")
        output.append(f"Resource Group: {result['resource_group']}")
        output.append(f"Total: {result['total_resources']} resources")
        output.append("=" * 40)
        
        for rtype, resources in result["grouped"].items():
            output.append(f"\n  {rtype}:")
            for r in resources:
                if isinstance(r, dict):
                    output.append(f"    • {r['name']} ({r.get('location', 'N/A')})")
                else:
                    output.append(f"    • {r}")
    
    elif "by_team" in result:
        # All resources grouped by team
        output.append(f"📦 ALL RESOURCES")
        output.append(f"Resource Group: {result['resource_group']}")
        output.append(f"Total: {result['total_resources']} resources")
        output.append("=" * 40)
        
        for team, resources in result["by_team"].items():
            output.append(f"\n  Team: {team}")
            for r in resources:
                output.append(f"    • {r['name']} ({r['type']})")
    
    return "\n".join(output)


@tool
def cost_api_tool(query: str) -> str:
    """
    Get real-time cloud cost data and resource information from Azure.
    
    Use this tool when you need:
    - Current spending for a team
    - Budget status and thresholds
    - Cost breakdown by resource type
    - Spending trends and anomalies
    - Subscription-level costs
    - List of deployed resources (storage accounts, containers, VMs, etc.)
    - Infrastructure information for a team
    
    Args:
        query: Query about costs or resources. Include team name if asking about specific team.
               Examples: 
               - "release team spending"
               - "all teams summary" 
               - "what storage accounts does the release team have"
               - "list all resources"
               - "show ci team infrastructure"
    
    Returns:
        Cost data with budget status and breakdown, or resource information
    """
    tool_instance = get_cost_tool()
    query_lower = query.lower()
    data_source = tool_instance.provider.provider_name.upper()
    mode_indicator = "🔴 LIVE" if is_live_mode() else "🟡 MOCK"
    
    # Extract team name from query
    team = _extract_team_from_query(query_lower, tool_instance.provider)
    
    # ============================================
    # RESOURCE QUERIES (NEW)
    # ============================================
    
    if _is_resource_query(query_lower):
        # Storage account queries
        if "storage" in query_lower:
            result = tool_instance.get_storage_accounts(team)
            response = _format_resources_response(result)
            return f"{response}\n\n[{data_source} {mode_indicator}]"
        
        # Container queries
        if "container" in query_lower:
            result = tool_instance.get_container_instances(team)
            response = _format_resources_response(result)
            return f"{response}\n\n[{data_source} {mode_indicator}]"
        
        # General resource queries
        if team:
            result = tool_instance.get_team_resources(team)
        else:
            result = tool_instance.get_all_resources()
        
        response = _format_resources_response(result)
        return f"{response}\n\n[{data_source} {mode_indicator}]"
    
    # ============================================
    # COST QUERIES (EXISTING)
    # ============================================
    
    # All teams summary
    if "all team" in query_lower or "summary" in query_lower or "overview" in query_lower:
        result = tool_instance.get_all_teams_summary()
        
        output = [f"📊 ALL TEAMS COST SUMMARY ({data_source} {mode_indicator})", "=" * 40]
        for team_data in result["teams"]:
            output.append(f"{team_data['status']} {team_data['team']}: {team_data['spend']} / {team_data['budget']} ({team_data['percentage']})")
        output.append("-" * 40)
        output.append(f"TOTAL: {result['totals']['total_spend']} / {result['totals']['total_budget']} ({result['totals']['overall_percentage']})")
        return "\n".join(output)
    
    # Specific subscription
    if "sub-" in query_lower:
        match = re.search(r'sub-[\w-]+', query_lower)
        if match:
            sub_id = match.group(0)
            result = tool_instance.get_subscription_costs(sub_id)
            if result["success"]:
                return f"Subscription {sub_id}: {result['total_cost']} (owned by {result['owning_team']})"
            return result["error"]
    
    # Team spending
    if team:
        result = tool_instance.get_team_spending(team)
        if not result["success"]:
            return result["error"]
        
        output = [
            f"💰 COST DATA: {result['team_name']} ({data_source} {mode_indicator})",
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
