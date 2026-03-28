"""Mock data provider for development and testing."""

import copy
from datetime import datetime
from typing import Any, Dict, List, Optional
from .base_provider import CostDataProvider
from ..g import g


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

RESOURCE_DISCOVERY_BASE = {
    "ci-team": {
        "team_name": "CI Team",
        "resource_group": "rg-ci-team",
        "idle_resources": [
            {
                "resource_id": "res-ci-build-vm-01",
                "resource_type": "vm",
                "team": "ci-team",
                "monthly_cost": 210.0,
                "days_idle": 18,
                "region": "eastus",
            },
            {
                "resource_id": "res-ci-build-cache-sa",
                "resource_type": "storage-account",
                "team": "ci-team",
                "monthly_cost": 74.0,
                "days_idle": 25,
                "region": "eastus2",
            },
        ],
        "orphaned_resources": [
            {
                "resource_id": "res-ci-orphan-disk-01",
                "resource_type": "managed-disk",
                "team": "ci-team",
                "monthly_cost": 38.0,
                "days_idle": 27,
                "region": "eastus",
                "reason_orphaned": "Parent VM was deleted but managed disk retained.",
            }
        ],
        "resource_utilization": {
            "average_cpu_percent": 22.4,
            "average_memory_percent": 30.9,
            "underutilized_count": 3,
        },
        "storage_accounts": [
            {"name": "stcibuildcache01", "location": "eastus2", "tags": {"team": "ci-team", "purpose": "build-cache"}}
        ],
        "container_instances": [
            {"name": "aci-ci-runner-legacy", "location": "eastus", "tags": {"team": "ci-team", "purpose": "legacy-runner"}}
        ],
    },
    "release-team": {
        "team_name": "Release Team",
        "resource_group": "rg-release-team",
        "idle_resources": [
            {
                "resource_id": "res-rel-canary-vm-01",
                "resource_type": "vm",
                "team": "release-team",
                "monthly_cost": 182.0,
                "days_idle": 15,
                "region": "eastus",
            },
            {
                "resource_id": "res-rel-canary-aci-01",
                "resource_type": "container-instance",
                "team": "release-team",
                "monthly_cost": 96.0,
                "days_idle": 19,
                "region": "eastus",
            },
        ],
        "orphaned_resources": [
            {
                "resource_id": "res-rel-orphan-ip-01",
                "resource_type": "public-ip",
                "team": "release-team",
                "monthly_cost": 15.0,
                "days_idle": 33,
                "region": "eastus",
                "reason_orphaned": "Load balancer was removed but public IP remained allocated.",
            }
        ],
        "resource_utilization": {
            "average_cpu_percent": 26.7,
            "average_memory_percent": 36.1,
            "underutilized_count": 4,
        },
        "storage_accounts": [
            {"name": "streleaseartifacts01", "location": "eastus", "tags": {"team": "release-team", "purpose": "artifacts"}}
        ],
        "container_instances": [
            {"name": "aci-release-preview-01", "location": "eastus", "tags": {"team": "release-team", "purpose": "preview"}}
        ],
    },
    "cloudops-team": {
        "team_name": "CloudOps Team",
        "resource_group": "rg-cloudops-team",
        "idle_resources": [
            {
                "resource_id": "res-ops-dr-vm-01",
                "resource_type": "vm",
                "team": "cloudops-team",
                "monthly_cost": 240.0,
                "days_idle": 14,
                "region": "eastus",
            },
            {
                "resource_id": "res-ops-audit-sa-01",
                "resource_type": "storage-account",
                "team": "cloudops-team",
                "monthly_cost": 82.0,
                "days_idle": 22,
                "region": "centralus",
            },
        ],
        "orphaned_resources": [
            {
                "resource_id": "res-ops-orphan-snapshot-01",
                "resource_type": "snapshot",
                "team": "cloudops-team",
                "monthly_cost": 44.0,
                "days_idle": 31,
                "region": "eastus",
                "reason_orphaned": "Source disk was removed after DR test; snapshot left behind.",
            }
        ],
        "resource_utilization": {
            "average_cpu_percent": 28.3,
            "average_memory_percent": 38.5,
            "underutilized_count": 3,
        },
        "storage_accounts": [
            {"name": "stcloudopslogs01", "location": "centralus", "tags": {"team": "cloudops-team", "purpose": "ops-logs"}}
        ],
        "container_instances": [
            {"name": "aci-dr-healthcheck-01", "location": "eastus", "tags": {"team": "cloudops-team", "purpose": "dr-check"}}
        ],
    },
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

    def _get_team_profile(self, team_id: str) -> Dict[str, Any]:
        return self.data.get(team_id, {})

    def _require_scenario_run(self) -> Optional[Any]:
        return getattr(g, "scenario_run", None)

    def _missing_scenario_error(self) -> dict:
        return {
            "success": False,
            "error": "Mock scenario not selected. Select one of the numbered scenarios before querying mock data.",
        }

    def _get_team_display_name(self, team_id: str) -> str:
        profile = self._get_team_profile(team_id)
        if profile.get("team_name"):
            return profile["team_name"]
        return team_id.replace("-", " ").title()

    def _get_team_budget(self, team_id: str) -> float:
        profile = self._get_team_profile(team_id)
        return float(profile.get("budget_monthly", 2400.0))

    def _build_scenario_cost_summary(self, team_data: Dict[str, Any], days: int = 30) -> Dict[str, Any]:
        normalized = team_data["team_id"]
        daily_costs = team_data.get("daily_costs", [])
        recent_days = daily_costs[-days:] if daily_costs else []

        spend_sum = sum(float(c.get("total_cost", 0)) for c in recent_days)
        recent_window = recent_days[-7:] if recent_days else []
        baseline_window = recent_days[: min(7, len(recent_days))] if recent_days else []
        baseline_avg = (
            sum(float(c.get("total_cost", 0)) for c in baseline_window) / len(baseline_window)
            if baseline_window else 0.0
        )
        recent_avg = (
            sum(float(c.get("total_cost", 0)) for c in recent_window) / len(recent_window)
            if recent_window else 0.0
        )
        spike_delta = recent_avg - baseline_avg
        budget = self._get_team_budget(normalized)
        budget_pct = (spend_sum / budget) * 100 if budget else 0.0
        profile = self._get_team_profile(normalized)

        return {
            "team_id": normalized,
            "team_name": self._get_team_display_name(normalized),
            "lead": profile.get("lead", f"{self._get_team_display_name(normalized)} Lead"),
            "subscriptions": profile.get("subscriptions", ["sub-mock-001"]),
            "monthly_budget": budget,
            "current_spend": spend_sum,
            "forecast_month_end": spend_sum * 1.2,
            "budget_used_percentage": budget_pct,
            "budget_status": self._get_budget_status(budget_pct),
            "compute_cost": sum(float(c.get("compute_cost", 0)) for c in recent_days),
            "storage_cost": sum(float(c.get("storage_cost", 0)) for c in recent_days),
            "network_cost": sum(float(c.get("network_cost", 0)) for c in recent_days),
            "daily_trend": [float(c.get("total_cost", 0)) for c in recent_days[-7:]] if recent_days else [],
            "baseline_daily_avg": baseline_avg,
            "recent_daily_avg": recent_avg,
            "daily_spike_delta": spike_delta,
        }

    def _build_resource_profiles(self, scenario_run: Optional[Any]) -> Dict[str, Dict[str, Any]]:
        if scenario_run is None:
            return {}

        profiles: Dict[str, Dict[str, Any]] = {}
        for team_data in scenario_run.cost_data.get("teams", []):
            team_id = team_data.get("team_id", "")
            profile = self._get_team_profile(team_id)
            resources = team_data.get("resources", [])

            storage_accounts = []
            container_instances = []
            for resource in resources:
                normalized_type = str(resource.get("type", "")).lower()
                entry = {
                    "name": resource.get("name", resource.get("resource_id", "unknown")),
                    "location": resource.get("region", "unknown"),
                    "tags": resource.get("tags", {}),
                }
                if "storage" in normalized_type:
                    storage_accounts.append(entry)
                if "container" in normalized_type:
                    container_instances.append(entry)

            profiles[team_id] = {
                "team_name": profile.get("team_name", team_id.replace("-", " ").title()),
                "resource_group": profile.get("resource_group", f"rg-{team_id}"),
                "scenario_resources": resources,
                "idle_resources": [],
                "orphaned_resources": [],
                "resource_utilization": {
                    "average_cpu_percent": 0.0,
                    "average_memory_percent": 0.0,
                    "underutilized_count": 0,
                },
                "storage_accounts": storage_accounts,
                "container_instances": container_instances,
            }
        return profiles

    def _compose_resource_rows(self, profile: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for item in profile.get("scenario_resources", []):
            daily_cost = item.get("daily_cost", [])
            monthly_cost = sum(float(c.get("cost", 0)) for c in daily_cost)
            rows.append(
                {
                    "name": item.get("resource_id", item.get("name", "unknown")),
                    "type": item.get("type", "unknown"),
                    "location": item.get("region", "unknown"),
                    "team": item.get("tags", {}).get("team"),
                    "monthly_cost": monthly_cost,
                    "days_idle": 0,
                    "status": "active",
                }
            )
        for item in profile["idle_resources"]:
            rows.append(
                {
                    "name": item["resource_id"],
                    "type": item["resource_type"],
                    "location": item["region"],
                    "team": item["team"],
                    "monthly_cost": item["monthly_cost"],
                    "days_idle": item["days_idle"],
                    "status": "idle",
                }
            )
        for item in profile["orphaned_resources"]:
            rows.append(
                {
                    "name": item["resource_id"],
                    "type": item["resource_type"],
                    "location": item["region"],
                    "team": item["team"],
                    "monthly_cost": item["monthly_cost"],
                    "days_idle": item["days_idle"],
                    "status": "orphaned",
                    "reason_orphaned": item["reason_orphaned"],
                }
            )
        return rows

    def _build_grouped_resources(self, rows: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for row in rows:
            key = row["type"].replace("-", " ").title()
            grouped.setdefault(key, []).append({"name": row["name"], "location": row["location"]})
        return grouped
    
    def get_team_spending(self, team_name: str, days: int = 30) -> dict:
        normalized = self._normalize_team_name(team_name)
        scenario_run = self._require_scenario_run()
        if scenario_run is None:
            return self._missing_scenario_error()

        cost_data = scenario_run.cost_data
        team_data = next((t for t in cost_data["teams"] if t["team_id"] == normalized), None)
        if not team_data:
            return {"success": False, "error": f"Team '{team_name}' not found."}

        summary = self._build_scenario_cost_summary(team_data, days=days)
        anomalies = ["Scenario active"]
        if summary["daily_spike_delta"] > 0:
            anomalies.append(
                f"Recent daily average increased by ${summary['daily_spike_delta']:.2f} versus the scenario baseline."
            )

        return {
            "success": True,
            "team_name": summary["team_name"],
            "lead": summary["lead"],
            "period": f"Last {days} days",
            "retrieved_at": datetime.now().isoformat(),
            "data_source": f"mock ({scenario_run.scenario_id})",
            "budget": {
                "monthly_budget": f"${summary['monthly_budget']:,.0f}",
                "current_spend": f"${summary['current_spend']:,.2f}",
                "forecast_month_end": f"${summary['forecast_month_end']:,.2f}",
                "budget_used_percentage": f"{summary['budget_used_percentage']:.1f}%",
                "budget_status": summary["budget_status"]
            },
            "subscriptions": summary["subscriptions"],
            "cost_breakdown": {
                "compute": f"${summary['compute_cost']:,.2f}",
                "storage": f"${summary['storage_cost']:,.2f}",
                "network": f"${summary['network_cost']:,.2f}"
            },
            "daily_trend": summary["daily_trend"],
            "anomalies": anomalies
        }
    
    def get_all_teams_summary(self) -> dict:
        scenario_run = self._require_scenario_run()
        teams = []
        total_budget = 0
        total_spend = 0
        if scenario_run is None:
            return self._missing_scenario_error()

        cost_data = scenario_run.cost_data
        primary_driver = None
        for team_data in cost_data["teams"]:
            summary = self._build_scenario_cost_summary(team_data)
            total_budget += summary["monthly_budget"]
            total_spend += summary["current_spend"]
            teams.append({
                "team": summary["team_name"],
                "team_id": summary["team_id"],
                "budget": f"${summary['monthly_budget']:,.0f}",
                "spend": f"${summary['current_spend']:,.2f}",
                "percentage": f"{summary['budget_used_percentage']:.1f}%",
                "status": "⚠️ OVER" if summary["budget_used_percentage"] > 100 else "✅ OK",
                "baseline_daily_avg": summary["baseline_daily_avg"],
                "recent_daily_avg": summary["recent_daily_avg"],
                "daily_spike_delta": summary["daily_spike_delta"],
            })

            if (
                primary_driver is None
                or summary["daily_spike_delta"] > primary_driver["daily_spike_delta"]
            ):
                primary_driver = {
                    "team": summary["team_name"],
                    "team_id": summary["team_id"],
                    "daily_spike_delta": summary["daily_spike_delta"],
                    "baseline_daily_avg": summary["baseline_daily_avg"],
                    "recent_daily_avg": summary["recent_daily_avg"],
                }

        return {
            "success": True,
            "retrieved_at": datetime.now().isoformat(),
            "data_source": f"mock ({scenario_run.scenario_id})",
            "teams": teams,
            "primary_driver": primary_driver,
            "totals": {
                "total_budget": f"${total_budget:,}",
                "total_spend": f"${total_spend:,.2f}",
                "overall_percentage": f"{(total_spend/total_budget)*100:.1f}%" if total_budget else "0%"
            }
        }
    
    def get_subscription_costs(self, subscription_id: str, days: int = 7) -> dict:
        scenario_run = self._require_scenario_run()
        if scenario_run is None:
            return self._missing_scenario_error()

        unalloc_sum = sum(float(c.get("total", 0)) for c in scenario_run.cost_data.get("unallocated_cost", [])[-days:])
        return {
            "success": True,
            "subscription_id": subscription_id,
            "owning_team": "Unknown" if unalloc_sum > 0 else "Multiple",
            "period": f"Last {days} days",
            "total_cost": f"${unalloc_sum:,.2f}",
            "daily_average": f"${unalloc_sum/days:,.2f}",
            "data_source": f"mock ({scenario_run.scenario_id})"
        }

    def get_team_resources(self, team_name: str) -> dict:
        scenario_run = self._require_scenario_run()
        if scenario_run is None:
            return self._missing_scenario_error()
        profiles = self._build_resource_profiles(scenario_run)
        normalized = self._normalize_team_name(team_name)

        if normalized not in profiles:
            return {
                "success": False,
                "error": f"Team '{team_name}' not found. Available: {', '.join(profiles.keys())}",
            }

        profile = profiles[normalized]
        resources = self._compose_resource_rows(profile)

        return {
            "success": True,
            "team": profile["team_name"],
            "lead": self.data.get(normalized, {}).get("lead", "Unknown"),
            "resource_group": profile["resource_group"],
            "total_resources": len(resources),
            "resources": resources,
            "grouped": self._build_grouped_resources(resources),
            "idle_resources": profile["idle_resources"],
            "orphaned_resources": profile["orphaned_resources"],
            "resource_utilization": profile["resource_utilization"],
            "retrieved_at": datetime.now().isoformat(),
            "data_source": f"mock ({scenario_run.scenario_id})" if scenario_run is not None else "mock",
        }

    def get_all_resources(self) -> dict:
        scenario_run = self._require_scenario_run()
        if scenario_run is None:
            return self._missing_scenario_error()
        profiles = self._build_resource_profiles(scenario_run)

        by_team: Dict[str, List[Dict[str, Any]]] = {}
        team_resource_health: Dict[str, Dict[str, Any]] = {}
        total_resources = 0

        for team_id, profile in profiles.items():
            resources = self._compose_resource_rows(profile)
            total_resources += len(resources)
            by_team[profile["team_name"]] = [
                {"name": r["name"], "type": r["type"], "location": r["location"]} for r in resources
            ]
            team_resource_health[team_id] = {
                "idle_resources": profile["idle_resources"],
                "orphaned_resources": profile["orphaned_resources"],
                "resource_utilization": profile["resource_utilization"],
            }

        return {
            "success": True,
            "resource_group": "rg-imrag-dev",
            "total_resources": total_resources,
            "by_team": by_team,
            "team_resource_health": team_resource_health,
            "retrieved_at": datetime.now().isoformat(),
            "data_source": f"mock ({scenario_run.scenario_id})" if scenario_run is not None else "mock",
        }

    def get_storage_accounts(self, team_name: str = None) -> dict:
        scenario_run = self._require_scenario_run()
        if scenario_run is None:
            return self._missing_scenario_error()
        profiles = self._build_resource_profiles(scenario_run)

        team_resource_health: Dict[str, Dict[str, Any]] = {}
        storage_accounts: List[Dict[str, Any]] = []

        if team_name:
            normalized = self._normalize_team_name(team_name)
            if normalized not in profiles:
                return {
                    "success": False,
                    "error": f"Team '{team_name}' not found. Available: {', '.join(profiles.keys())}",
                }

            profile = profiles[normalized]
            for account in profile["storage_accounts"]:
                storage_accounts.append(
                    {
                        "name": account["name"],
                        "location": account["location"],
                        "team": profile["team_name"],
                        "tags": account.get("tags", {}),
                    }
                )

            team_resource_health[normalized] = {
                "idle_resources": profile["idle_resources"],
                "orphaned_resources": profile["orphaned_resources"],
                "resource_utilization": profile["resource_utilization"],
            }
            team_label = profile["team_name"]
        else:
            for team_id, profile in profiles.items():
                team_resource_health[team_id] = {
                    "idle_resources": profile["idle_resources"],
                    "orphaned_resources": profile["orphaned_resources"],
                    "resource_utilization": profile["resource_utilization"],
                }
                for account in profile["storage_accounts"]:
                    storage_accounts.append(
                        {
                            "name": account["name"],
                            "location": account["location"],
                            "team": profile["team_name"],
                            "tags": account.get("tags", {}),
                        }
                    )
            team_label = None

        return {
            "success": True,
            "team": team_label,
            "count": len(storage_accounts),
            "storage_accounts": storage_accounts,
            "team_resource_health": team_resource_health,
            "retrieved_at": datetime.now().isoformat(),
            "data_source": f"mock ({scenario_run.scenario_id})" if scenario_run is not None else "mock",
        }

    def get_container_instances(self, team_name: str = None) -> dict:
        scenario_run = self._require_scenario_run()
        if scenario_run is None:
            return self._missing_scenario_error()
        profiles = self._build_resource_profiles(scenario_run)

        team_resource_health: Dict[str, Dict[str, Any]] = {}
        container_instances: List[Dict[str, Any]] = []

        if team_name:
            normalized = self._normalize_team_name(team_name)
            if normalized not in profiles:
                return {
                    "success": False,
                    "error": f"Team '{team_name}' not found. Available: {', '.join(profiles.keys())}",
                }

            profile = profiles[normalized]
            for container in profile["container_instances"]:
                container_instances.append(
                    {
                        "name": container["name"],
                        "location": container["location"],
                        "team": profile["team_name"],
                        "tags": container.get("tags", {}),
                    }
                )

            team_resource_health[normalized] = {
                "idle_resources": profile["idle_resources"],
                "orphaned_resources": profile["orphaned_resources"],
                "resource_utilization": profile["resource_utilization"],
            }
            team_label = profile["team_name"]
        else:
            for team_id, profile in profiles.items():
                team_resource_health[team_id] = {
                    "idle_resources": profile["idle_resources"],
                    "orphaned_resources": profile["orphaned_resources"],
                    "resource_utilization": profile["resource_utilization"],
                }
                for container in profile["container_instances"]:
                    container_instances.append(
                        {
                            "name": container["name"],
                            "location": container["location"],
                            "team": profile["team_name"],
                            "tags": container.get("tags", {}),
                        }
                    )
            team_label = None

        return {
            "success": True,
            "team": team_label,
            "count": len(container_instances),
            "container_instances": container_instances,
            "team_resource_health": team_resource_health,
            "retrieved_at": datetime.now().isoformat(),
            "data_source": f"mock ({scenario_run.scenario_id})" if scenario_run is not None else "mock",
        }
