import copy
from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass
class ScenarioRun:
    scenario_id: str
    cost_data: Dict[str, Any]
    pipeline_data: Dict[str, Any]

SCENARIO_IDS = [
    "scenario_1_vm_destroy",
    "scenario_2_tagging",
    "scenario_3_autoscaler",
    "scenario_4_forgotten_poc",
    "scenario_5_app_misconfig",
    "scenario_legacy_mock",
]

# Base template for cost
# Base template for pipelines
BASE_COST = {
    "subscription_id": "sub-mock-001",
    "teams": [
        {
            "team_id": "ci-team",
            "daily_costs": [],
            "resources": []
        },
        {
            "team_id": "release-team",
            "daily_costs": [],
            "resources": []
        },
        {
            "team_id": "cloudops-team",
            "daily_costs": [],
            "resources": []
        }
    ],
    "unallocated_cost": [
        {"date": f"2025-01-{i:02d}", "total": 0.0} for i in range(1, 31)
    ]
}

def _get_team(cost_data, team_id):
    for team in cost_data["teams"]:
        if team["team_id"] == team_id:
            return team
    return None

def _base_pipelines():
    return {"pipelines": []}

def _build_scenario_1_vm_destroy() -> ScenarioRun:
    cost = copy.deepcopy(BASE_COST)
    pipes = _base_pipelines()
    
    # ci-team cost spikes on day 10
    ci_team = _get_team(cost, "ci-team")
    rel_team = _get_team(cost, "release-team")
    ops_team = _get_team(cost, "cloudops-team")
    
    # Normal usage for others
    for i in range(1, 31):
        date_str = f"2025-01-{i:02d}"
        ci_tot = 100.0 if i < 10 else 300.0 # Spike
        ci_team["daily_costs"].append({"date": date_str, "total_cost": ci_tot, "compute_cost": ci_tot * 0.7, "storage_cost": ci_tot * 0.2, "network_cost": ci_tot * 0.1})
        rel_team["daily_costs"].append({"date": date_str, "total_cost": 150.0, "compute_cost": 100.0, "storage_cost": 30.0, "network_cost": 20.0})
        ops_team["daily_costs"].append({"date": date_str, "total_cost": 200.0, "compute_cost": 140.0, "storage_cost": 40.0, "network_cost": 20.0})
    
    # Pipelines
    pipes["pipelines"].append({
        "pipeline_id": "pipe-deploy-loadtest",
        "name": "deploy-loadtest",
        "team_id": "ci-team",
        "status": "success",
        "started_at": "2025-01-09T10:00:00Z",
        "finished_at": "2025-01-09T10:05:00Z",
        "jobs": [{"job_id": "job-1", "name": "terraform-apply", "status": "success"}]
    })
    
    for i, date in enumerate(("01-10", "01-11", "01-12")):
        pipes["pipelines"].append({
            "pipeline_id": f"pipe-fail-destroy-{i}",
            "name": "destroy-loadtest",
            "team_id": "ci-team",
            "status": "failed",
            "started_at": f"2025-{date}T10:00:00Z",
            "finished_at": f"2025-{date}T10:05:00Z",
            "jobs": [{"job_id": "job-d", "name": "terraform-destroy", "status": "failed", "log_excerpt": "Error: Error acquiring the state lock"}]
        })
        
    pipes["pipelines"].append({
        "pipeline_id": "pipe-decoy-fail",
        "name": "deploy-feature-x",
        "team_id": "ci-team",
        "status": "failed",
        "started_at": "2025-01-11T14:00:00Z",
        "finished_at": "2025-01-11T14:05:00Z",
        "jobs": [{"job_id": "job-t", "name": "unit-tests", "status": "failed", "log_excerpt": "AssertionError: Expected 200, got 500"}]
    })
    
    # Resources
    num = 1
    for t in [ci_team, rel_team, ops_team]:
        for i in range(5):
            t["resources"].append({
                "resource_id": f"res-{num}", "name": f"res-{t['team_id']}-{i}", "type": "vm",
                "tags": {"team": t['team_id'], "env": "prod"}, "region": "eastus", "sku": "Standard", "daily_cost": [{"date": "2025-01-01", "cost": 10.0}], "created_at": "2024-01-01"
            })
            num += 1
            
    ci_team["resources"].append({
        "resource_id": "res-loadtest-1", "name": "vm-loadtest-1", "type": "vm", "tags": {"team": "ci-team", "env": "loadtest"}, "region": "eastus", "sku": "Standard", "daily_cost": [{"date": "2025-01-10", "cost": 200.0}], "created_at": "2025-01-09T10:00:00Z"
    })
    ci_team["resources"].append({
        "resource_id": "res-loadtest-2", "name": "vm-loadtest-2", "type": "vm", "tags": {"team": "ci-team", "env": "loadtest"}, "region": "eastus", "sku": "Standard", "daily_cost": [{"date": "2025-01-11", "cost": 195.0}], "created_at": "2025-01-09T10:00:00Z"
    })
            
    return ScenarioRun("scenario_1_vm_destroy", cost, pipes)

def _build_scenario_2_tagging() -> ScenarioRun:
    cost = copy.deepcopy(BASE_COST)
    pipes = _base_pipelines()
    
    unalloc = cost["unallocated_cost"]
    rel_team = _get_team(cost, "release-team")
    ci_team = _get_team(cost, "ci-team")
    ops_team = _get_team(cost, "cloudops-team")
    
    for i in range(1, 31):
        date_str = f"2025-01-{i:02d}"
        # Decoy ci-team small increase
        ci_tot = 100.0 if i < 15 else 120.0
        ci_team["daily_costs"].append({"date": date_str, "total_cost": ci_tot, "compute_cost": ci_tot * 0.7, "storage_cost": ci_tot * 0.2, "network_cost": ci_tot * 0.1})
        rel_team["daily_costs"].append({"date": date_str, "total_cost": 150.0, "compute_cost": 100.0, "storage_cost": 30.0, "network_cost": 20.0})
        ops_team["daily_costs"].append({"date": date_str, "total_cost": 200.0, "compute_cost": 140.0, "storage_cost": 40.0, "network_cost": 20.0})
        
        # Unallocated increases 
        u_tot = 10.0 if i < 15 else 300.0
        unalloc[i-1]["total"] = u_tot
        
    pipes["pipelines"].append({
        "pipeline_id": "pipe-deploy-rel",
        "name": "deploy-release-prod",
        "team_id": "release-team",
        "status": "success",
        "started_at": "2025-01-14T10:00:00Z",
        "finished_at": "2025-01-14T10:05:00Z",
        "jobs": [{"job_id": "job-1", "name": "terraform-apply", "status": "success", "log_excerpt": "Updating tags... team=legacy"}]
    })
    
    rel_team["resources"].extend([
        {
            "resource_id": "res-db-prod", "name": "release-db-prod", "type": "db",
            "tags": {"team": "legacy"}, # Mistagged
            "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-14"
        },
        {
            "resource_id": "res-api-1", "name": "release-api-1", "type": "vm",
            "tags": {}, # Missing tag
            "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-14"
        }
    ])
    
    return ScenarioRun("scenario_2_tagging", cost, pipes)

def _build_scenario_3_autoscaler() -> ScenarioRun:
    cost = copy.deepcopy(BASE_COST)
    pipes = _base_pipelines()
    
    ci_team = _get_team(cost, "ci-team")
    rel_team = _get_team(cost, "release-team")
    ops_team = _get_team(cost, "cloudops-team")
    
    for i in range(1, 31):
        date_str = f"2025-01-{i:02d}"
        
        # Spike from day 10, stays high
        rel_tot = 150.0 if i < 10 else 450.0
        
        ci_team["daily_costs"].append({"date": date_str, "total_cost": 100.0, "compute_cost": 70.0, "storage_cost": 20.0, "network_cost": 10.0})
        rel_team["daily_costs"].append({"date": date_str, "total_cost": rel_tot, "compute_cost": rel_tot * 0.7, "storage_cost": rel_tot * 0.2, "network_cost": rel_tot * 0.1})
        ops_team["daily_costs"].append({"date": date_str, "total_cost": 200.0, "compute_cost": 140.0, "storage_cost": 40.0, "network_cost": 20.0})
        
    pipes["pipelines"].append({
        "pipeline_id": "pipe-update-as",
        "name": "update-web-autoscaler",
        "team_id": "release-team",
        "status": "success",
        "started_at": "2025-01-09T10:00:00Z",
        "finished_at": "2025-01-09T10:05:00Z",
        "jobs": [{"job_id": "job-1", "name": "deploy-config", "status": "success", "log_excerpt": "Updated HPA config limits"}]
    })
    
    rel_team["resources"].append({
        "resource_id": "res-web-frontend", "name": "web-frontend-asg", "type": "vmss",
        "tags": {"team": "release-team"}, "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-01",
        "metrics": "Instance count: 4 -> 12 on Jan 10. Current: 12. No scale-down events logged."
    })
    
    rel_team["resources"].append({
        "resource_id": "res-user-svc", "name": "user-service", "type": "vmss",
        "tags": {"team": "release-team"}, "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-01",
        "metrics": "Instance count: 2 -> 6 on Jan 10. Current: 2. Scaled back down OK."
    })
    
    return ScenarioRun("scenario_3_autoscaler", cost, pipes)

def _build_scenario_4_forgotten_poc() -> ScenarioRun:
    cost = copy.deepcopy(BASE_COST)
    pipes = _base_pipelines()
    
    ci_team = _get_team(cost, "ci-team")
    rel_team = _get_team(cost, "release-team")
    ops_team = _get_team(cost, "cloudops-team")
    
    for i in range(1, 31):
        date_str = f"2025-01-{i:02d}"
        
        ops_tot = 200.0 if i < 15 else 500.0
        
        ci_team["daily_costs"].append({"date": date_str, "total_cost": 100.0, "compute_cost": 70.0, "storage_cost": 20.0, "network_cost": 10.0})
        rel_team["daily_costs"].append({"date": date_str, "total_cost": 150.0, "compute_cost": 100.0, "storage_cost": 30.0, "network_cost": 20.0})
        ops_team["daily_costs"].append({"date": date_str, "total_cost": ops_tot, "compute_cost": ops_tot * 0.7, "storage_cost": ops_tot * 0.2, "network_cost": ops_tot * 0.1})
        
    pipes["pipelines"].append({
        "pipeline_id": "pipe-deploy-poc",
        "name": "deploy-poc-analytics",
        "team_id": "cloudops-team",
        "status": "success",
        "started_at": "2025-01-14T10:00:00Z",
        "finished_at": "2025-01-14T10:05:00Z",
        "jobs": [{"job_id": "job-1", "name": "terraform-apply", "status": "success"}]
    })
    
    pipes["pipelines"].append({
        "pipeline_id": "pipe-deploy-dash",
        "name": "deploy-poc-dashboard",
        "team_id": "cloudops-team",
        "status": "success",
        "started_at": "2025-01-10T10:00:00Z",
        "finished_at": "2025-01-10T10:05:00Z",
        "jobs": [{"job_id": "job-1", "name": "terraform-apply", "status": "success"}]
    })
    pipes["pipelines"].append({
        "pipeline_id": "pipe-destroy-dash",
        "name": "destroy-poc-dashboard",
        "team_id": "cloudops-team",
        "status": "success",
        "started_at": "2025-01-12T10:00:00Z",
        "finished_at": "2025-01-12T10:05:00Z",
        "jobs": [{"job_id": "job-1", "name": "terraform-destroy", "status": "success"}]
    })
    
    ops_team["resources"].extend([
        {
            "resource_id": "poc-analytics-vm-1", "name": "poc-analytics-vm-1", "type": "vm",
            "tags": {"env": "test", "project": "poc-analytics", "team": "cloudops-team"},
            "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-14",
            "metrics": "CPU utilization: ~0% after Jan 15"
        },
        {
            "resource_id": "poc-analytics-db", "name": "poc-analytics-db", "type": "db",
            "tags": {"env": "test", "project": "poc-analytics", "team": "cloudops-team"},
            "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-14"
        }
    ])
    
    return ScenarioRun("scenario_4_forgotten_poc", cost, pipes)

def _build_scenario_5_app_misconfig() -> ScenarioRun:
    cost = copy.deepcopy(BASE_COST)
    pipes = _base_pipelines()
    
    ci_team = _get_team(cost, "ci-team")
    rel_team = _get_team(cost, "release-team")
    ops_team = _get_team(cost, "cloudops-team")
    
    for i in range(1, 31):
        date_str = f"2025-01-{i:02d}"
        
        rel_tot = 150.0 if i < 20 else 600.0
        
        ci_team["daily_costs"].append({"date": date_str, "total_cost": 100.0, "compute_cost": 70.0, "storage_cost": 20.0, "network_cost": 10.0})
        rel_team["daily_costs"].append({"date": date_str, "total_cost": rel_tot, "compute_cost": rel_tot * 0.7, "storage_cost": rel_tot * 0.2, "network_cost": rel_tot * 0.1})
        ops_team["daily_costs"].append({"date": date_str, "total_cost": 200.0, "compute_cost": 140.0, "storage_cost": 40.0, "network_cost": 20.0})
        
    pipes["pipelines"].append({
        "pipeline_id": "pipe-deploy-rel-api",
        "name": "deploy-release-api",
        "team_id": "release-team",
        "status": "success",
        "started_at": "2025-01-19T10:00:00Z",
        "finished_at": "2025-01-19T10:05:00Z",
        "jobs": [{"job_id": "job-1", "name": "deploy-k8s", "status": "success", "log_excerpt": "Config update: MAX_WORKERS=500"}]
    })
    
    pipes["pipelines"].append({
        "pipeline_id": "pipe-deploy-ops",
        "name": "deploy-cloudops-service",
        "team_id": "cloudops-team",
        "status": "success",
        "started_at": "2025-01-19T12:00:00Z",
        "finished_at": "2025-01-19T12:05:00Z",
        "jobs": [{"job_id": "job-1", "name": "deploy-k8s", "status": "success"}]
    })
    
    rel_team["resources"].append({
            "resource_id": "rel-api-pods", "name": "release-api", "type": "k8s-deployment",
            "tags": {"team": "release-team"},
            "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-01",
            "metrics": "Pod count jump from 5 to 50 on Jan 19. Repeated app logs 'failed to process message, retrying'."
    })
    
    return ScenarioRun("scenario_5_app_misconfig", cost, pipes)


def _build_scenario_legacy_mock() -> ScenarioRun:
    cost = copy.deepcopy(BASE_COST)
    pipes = _base_pipelines()

    ci_team = _get_team(cost, "ci-team")
    rel_team = _get_team(cost, "release-team")
    ops_team = _get_team(cost, "cloudops-team")

    legacy_daily = {
        "ci-team": 1850.0 / 30.0,
        "release-team": 2650.0 / 30.0,
        "cloudops-team": 3200.0 / 30.0,
    }

    for i in range(1, 31):
        date_str = f"2025-01-{i:02d}"
        for team in (ci_team, rel_team, ops_team):
            team_id = team["team_id"]
            total_cost = legacy_daily[team_id]
            team["daily_costs"].append(
                {
                    "date": date_str,
                    "total_cost": total_cost,
                    "compute_cost": total_cost * 0.65,
                    "storage_cost": total_cost * 0.2,
                    "network_cost": total_cost * 0.1,
                }
            )

    pipes["pipelines"].extend([
        {
            "pipeline_id": "pipe-legacy-rel-1",
            "name": "deploy-new-api-gateway",
            "team_id": "release-team",
            "status": "success",
            "started_at": "2025-01-27T10:00:00Z",
            "finished_at": "2025-01-27T10:20:00Z",
            "jobs": [{"job_id": "legacy-rel-1", "name": "terraform-apply", "status": "success"}],
        },
        {
            "pipeline_id": "pipe-legacy-rel-2",
            "name": "scale-release-infra",
            "team_id": "release-team",
            "status": "success",
            "started_at": "2025-01-25T10:00:00Z",
            "finished_at": "2025-01-25T10:35:00Z",
            "jobs": [{"job_id": "legacy-rel-2", "name": "vm-provisioning", "status": "success"}],
        },
        {
            "pipeline_id": "pipe-legacy-ci-1",
            "name": "optimize-build-cache",
            "team_id": "ci-team",
            "status": "success",
            "started_at": "2025-01-28T08:00:00Z",
            "finished_at": "2025-01-28T08:15:00Z",
            "jobs": [{"job_id": "legacy-ci-1", "name": "update-cache", "status": "success"}],
        },
        {
            "pipeline_id": "pipe-legacy-ops-1",
            "name": "dr-failover-test",
            "team_id": "cloudops-team",
            "status": "success",
            "started_at": "2025-01-26T09:00:00Z",
            "finished_at": "2025-01-26T10:00:00Z",
            "jobs": [{"job_id": "legacy-ops-1", "name": "scale-dr-region", "status": "success"}],
        },
    ])

    return ScenarioRun("scenario_legacy_mock", cost, pipes)

def build_scenario_run(scenario_id: str) -> ScenarioRun:
    if scenario_id == "scenario_1_vm_destroy":
        return _build_scenario_1_vm_destroy()
    elif scenario_id == "scenario_2_tagging":
        return _build_scenario_2_tagging()
    elif scenario_id == "scenario_3_autoscaler":
        return _build_scenario_3_autoscaler()
    elif scenario_id == "scenario_4_forgotten_poc":
        return _build_scenario_4_forgotten_poc()
    elif scenario_id == "scenario_5_app_misconfig":
        return _build_scenario_5_app_misconfig()
    elif scenario_id == "scenario_legacy_mock":
        return _build_scenario_legacy_mock()
    else:
        raise ValueError(f"Unknown scenario ID: {scenario_id}")
