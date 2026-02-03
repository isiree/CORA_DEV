"""Azure Cost Management API provider using DefaultAzureCredential."""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from azure.mgmt.resource import ResourceManagementClient
from .base_provider import CostDataProvider

logger = logging.getLogger(__name__)

# Clear empty Azure env vars that confuse DefaultAzureCredential
for var in ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"]:
    if os.getenv(var) == "":
        os.environ.pop(var, None)

# Try to import Azure SDK
try:
    from azure.identity import DefaultAzureCredential, AzureCliCredential
    from azure.mgmt.costmanagement import CostManagementClient
    from azure.mgmt.costmanagement.models import (
        QueryDefinition, QueryTimePeriod, QueryDataset,
        QueryAggregation, QueryGrouping, TimeframeType,
        GranularityType, ExportType
    )
    from azure.core.exceptions import HttpResponseError
    AZURE_SDK_AVAILABLE = True
except ImportError:
    AZURE_SDK_AVAILABLE = False
    logger.warning("Azure SDK not installed. Run: pip install azure-identity azure-mgmt-costmanagement azure-mgmt-resource")


# Team configuration - maps teams to their resources via tags
TEAM_CONFIG = {
    "release-team": {
        "display_name": "Release Team",
        "lead": "Alex Johnson",
        "resource_group": "rg-imrag-dev",
        "tag_filter": {"team": "release"},  # Filter by tag
        "monthly_budget": 15.0
    },
    "ci-team": {
        "display_name": "CI Team",
        "lead": "James Wilson",
        "resource_group": "rg-imrag-dev",
        "tag_filter": {"team": "ci"},  # Filter by tag
        "monthly_budget": 10.0
    },
    "cloudops-team": {
        "display_name": "CloudOps Team",
        "lead": "David Brown",
        "resource_group": "rg-imrag-dev",
        "tag_filter": {"team": "cloudops"},  # Filter by tag
        "monthly_budget": 10.0
    }
}


class AzureCostDataProvider(CostDataProvider):
    """Azure Cost Management API provider."""
    
    SERVICE_CATEGORIES = {
        "virtual machines": "compute", "container": "compute", "functions": "compute",
        "storage": "storage", "blob": "storage", "disk": "storage",
        "network": "networking", "bandwidth": "networking", "load balancer": "networking",
        "sql": "database", "cosmos": "database", "postgresql": "database",
    }
    
    def __init__(self):
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID", "")
        self._credential = None
        self._client = None
        self._resource_client = None
        self.teams = TEAM_CONFIG
    
    @property
    def provider_name(self) -> str:
        return "azure"
    
    def _get_credential(self):
        """Get Azure credential - prefer CLI credential for simplicity."""
        if not AZURE_SDK_AVAILABLE:
            raise ImportError("Azure SDK not installed")
        
        if self._credential is None:
            try:
                cli_cred = AzureCliCredential()
                cli_cred.get_token("https://management.azure.com/.default")
                self._credential = cli_cred
                logger.info("Using Azure CLI credential")
            except Exception as cli_error:
                logger.debug(f"CLI credential failed: {cli_error}")
                self._credential = DefaultAzureCredential(
                    exclude_environment_credential=True,
                    exclude_managed_identity_credential=True,
                )
        return self._credential
    
    def _get_client(self):
        if self._client is None:
            self._client = CostManagementClient(
                credential=self._get_credential(),
                subscription_id=self.subscription_id
            )
        return self._client
    
    def _get_resource_client(self):
        """Get Azure Resource Management client."""
        if self._resource_client is None:
            self._resource_client = ResourceManagementClient(
                credential=self._get_credential(),
                subscription_id=self.subscription_id
            )
        return self._resource_client
    
    def is_available(self) -> bool:
        if not AZURE_SDK_AVAILABLE:
            logger.warning("Azure SDK not installed")
            return False
        if not self.subscription_id:
            logger.warning("AZURE_SUBSCRIPTION_ID not set")
            return False
        try:
            self._get_credential().get_token("https://management.azure.com/.default")
            return True
        except Exception as e:
            logger.error(f"Azure auth failed: {e}")
            return False
    
    def get_team_keys(self) -> List[str]:
        return list(self.teams.keys())
    
    def _normalize_team_name(self, team_name: str) -> str:
        return team_name.lower().replace(" ", "-").replace("_", "-")
    
    def _categorize_service(self, service_name: str) -> str:
        lower = service_name.lower()
        for pattern, category in self.SERVICE_CATEGORIES.items():
            if pattern in lower:
                return category
        return "other"
    
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
    
    # ============================================
    # RESOURCE DISCOVERY METHODS (NEW)
    # ============================================
    
    def get_team_resources(self, team_name: str) -> dict:
        """Get all resources for a team (filtered by tags)."""
        normalized = self._normalize_team_name(team_name)
        
        if normalized not in self.teams:
            return {
                "success": False,
                "error": f"Team '{team_name}' not found. Available: {', '.join(self.teams.keys())}"
            }
        
        team = self.teams[normalized]
        tag_filter = team.get("tag_filter", {})
        
        try:
            client = self._get_resource_client()
            resources = client.resources.list_by_resource_group(
                team['resource_group'],
                expand="createdTime,changedTime"
            )
            
            resource_list = []
            for resource in resources:
                # Filter by team tag if specified
                resource_tags = resource.tags or {}
                
                if tag_filter:
                    # Check if resource matches team's tag filter
                    matches = all(
                        resource_tags.get(k, "").lower() == v.lower() 
                        for k, v in tag_filter.items()
                    )
                    if not matches:
                        continue
                
                resource_list.append({
                    "name": resource.name,
                    "type": resource.type,
                    "kind": resource.kind,
                    "location": resource.location,
                    "created": str(resource.created_time) if resource.created_time else None,
                    "tags": resource_tags
                })
            
            # Group by resource type
            grouped = {}
            for r in resource_list:
                # Extract friendly type name (e.g., "Microsoft.Storage/storageAccounts" -> "Storage Accounts")
                type_parts = r["type"].split("/")
                if len(type_parts) >= 2:
                    rtype = type_parts[-1]
                    # Convert camelCase to Title Case
                    friendly_type = ''.join(' ' + c if c.isupper() else c for c in rtype).strip().title()
                else:
                    friendly_type = r["type"]
                
                if friendly_type not in grouped:
                    grouped[friendly_type] = []
                grouped[friendly_type].append({
                    "name": r["name"],
                    "location": r["location"]
                })
            
            return {
                "success": True,
                "team": team["display_name"],
                "lead": team["lead"],
                "resource_group": team["resource_group"],
                "total_resources": len(resource_list),
                "resources": resource_list,
                "grouped": grouped,
                "retrieved_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting resources: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_all_resources(self) -> dict:
        """Get all resources in the resource group (not filtered by team)."""
        try:
            client = self._get_resource_client()
            resource_group = "rg-imrag-dev"
            
            resources = client.resources.list_by_resource_group(
                resource_group,
                expand="createdTime,changedTime"
            )
            
            resource_list = []
            for resource in resources:
                resource_tags = resource.tags or {}
                team_tag = resource_tags.get("team", "unassigned")
                
                resource_list.append({
                    "name": resource.name,
                    "type": resource.type,
                    "location": resource.location,
                    "team": team_tag,
                    "tags": resource_tags
                })
            
            # Group by team
            by_team = {}
            for r in resource_list:
                team = r["team"]
                if team not in by_team:
                    by_team[team] = []
                by_team[team].append({
                    "name": r["name"],
                    "type": r["type"].split("/")[-1]
                })
            
            return {
                "success": True,
                "resource_group": resource_group,
                "total_resources": len(resource_list),
                "resources": resource_list,
                "by_team": by_team,
                "retrieved_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting all resources: {e}")
            return {"success": False, "error": str(e)}
    
    def get_storage_accounts(self, team_name: str = None) -> dict:
        """Get storage accounts, optionally filtered by team."""
        try:
            if team_name:
                result = self.get_team_resources(team_name)
                if not result["success"]:
                    return result
                
                storage_accounts = [
                    r for r in result["resources"] 
                    if "storageaccounts" in r["type"].lower()
                ]
                
                return {
                    "success": True,
                    "team": result["team"],
                    "storage_accounts": storage_accounts,
                    "count": len(storage_accounts)
                }
            else:
                # Get all storage accounts
                result = self.get_all_resources()
                if not result["success"]:
                    return result
                
                storage_accounts = [
                    r for r in result["resources"]
                    if "storageaccounts" in r["type"].lower()
                ]
                
                return {
                    "success": True,
                    "storage_accounts": storage_accounts,
                    "count": len(storage_accounts)
                }
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_container_instances(self, team_name: str = None) -> dict:
        """Get container instances, optionally filtered by team."""
        try:
            if team_name:
                result = self.get_team_resources(team_name)
            else:
                result = self.get_all_resources()
            
            if not result["success"]:
                return result
            
            containers = [
                r for r in result["resources"]
                if "containergroups" in r["type"].lower()
            ]
            
            return {
                "success": True,
                "team": result.get("team", "All Teams"),
                "container_instances": containers,
                "count": len(containers)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ============================================
    # COST METHODS (EXISTING)
    # ============================================
    
    def get_team_spending(self, team_name: str, days: int = 30) -> dict:
        normalized = self._normalize_team_name(team_name)
        
        if normalized not in self.teams:
            return {
                "success": False,
                "error": f"Team '{team_name}' not found. Available: {', '.join(self.teams.keys())}"
            }
        
        team = self.teams[normalized]
        
        try:
            client = self._get_client()
            scope = f"/subscriptions/{self.subscription_id}/resourceGroups/{team['resource_group']}"
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            query = QueryDefinition(
                type=ExportType.ACTUAL_COST,
                timeframe=TimeframeType.CUSTOM,
                time_period=QueryTimePeriod(from_property=start_date, to=end_date),
                dataset=QueryDataset(
                    granularity=GranularityType.NONE,
                    aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")},
                    grouping=[QueryGrouping(type="Dimension", name="ServiceName")]
                )
            )
            
            result = client.query.usage(scope=scope, parameters=query)
            
            total_cost = 0.0
            breakdown = {"compute": 0.0, "storage": 0.0, "networking": 0.0, "database": 0.0, "other": 0.0}
            
            if result.rows:
                for row in result.rows:
                    cost = float(row[0]) if row[0] else 0.0
                    service = row[1] if len(row) > 1 else "Unknown"
                    total_cost += cost
                    breakdown[self._categorize_service(service)] += cost
            
            breakdown = {k: round(v, 2) for k, v in breakdown.items()}
            budget = team["monthly_budget"]
            budget_pct = (total_cost / budget * 100) if budget > 0 else 0
            forecast = (total_cost / max(days, 1)) * 30
            
            return {
                "success": True,
                "team_name": team["display_name"],
                "lead": team["lead"],
                "period": f"Last {days} days",
                "retrieved_at": datetime.now().isoformat(),
                "data_source": "azure",
                "budget": {
                    "monthly_budget": f"${budget:,.2f}",
                    "current_spend": f"${total_cost:,.2f}",
                    "forecast_month_end": f"${forecast:,.2f}",
                    "budget_used_percentage": f"{budget_pct:.1f}%",
                    "budget_status": self._get_budget_status(budget_pct)
                },
                "subscriptions": [self.subscription_id],
                "cost_breakdown": {k: f"${v:,.2f}" for k, v in breakdown.items()},
                "daily_trend": [],
                "anomalies": ["Live data - check Azure portal for anomalies"]
            }
            
        except HttpResponseError as e:
            return {"success": False, "error": f"Azure API error: {str(e)}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_all_teams_summary(self) -> dict:
        teams_data = []
        total_budget = 0.0
        total_spend = 0.0
        
        for team_key in self.teams:
            result = self.get_team_spending(team_key)
            team = self.teams[team_key]
            
            if result["success"]:
                spend = float(result["budget"]["current_spend"].replace("$", "").replace(",", ""))
                budget = team["monthly_budget"]
                total_budget += budget
                total_spend += spend
                budget_pct = (spend / budget * 100) if budget > 0 else 0
                
                teams_data.append({
                    "team": team["display_name"],
                    "budget": f"${budget:,.2f}",
                    "spend": f"${spend:,.2f}",
                    "percentage": f"{budget_pct:.1f}%",
                    "status": "⚠️ OVER" if budget_pct > 100 else "✅ OK"
                })
            else:
                teams_data.append({
                    "team": team["display_name"],
                    "budget": f"${team['monthly_budget']:,.2f}",
                    "spend": "Error",
                    "percentage": "N/A",
                    "status": "❌ ERROR"
                })
        
        return {
            "success": True,
            "retrieved_at": datetime.now().isoformat(),
            "data_source": "azure",
            "teams": teams_data,
            "totals": {
                "total_budget": f"${total_budget:,.2f}",
                "total_spend": f"${total_spend:,.2f}",
                "overall_percentage": f"{(total_spend/total_budget)*100:.1f}%" if total_budget > 0 else "N/A"
            }
        }
    
    def get_subscription_costs(self, subscription_id: str, days: int = 7) -> dict:
        try:
            client = self._get_client()
            scope = f"/subscriptions/{self.subscription_id}"
            
            query = QueryDefinition(
                type=ExportType.ACTUAL_COST,
                timeframe=TimeframeType.CUSTOM,
                time_period=QueryTimePeriod(
                    from_property=datetime.now() - timedelta(days=days),
                    to=datetime.now()
                ),
                dataset=QueryDataset(
                    granularity=GranularityType.NONE,
                    aggregation={"totalCost": QueryAggregation(name="Cost", function="Sum")}
                )
            )
            
            result = client.query.usage(scope=scope, parameters=query)
            total = float(result.rows[0][0]) if result.rows else 0.0
            
            return {
                "success": True,
                "subscription_id": subscription_id,
                "owning_team": "All Teams",
                "period": f"Last {days} days",
                "total_cost": f"${total:.2f}",
                "daily_average": f"${total/days:.2f}",
                "data_source": "azure"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}