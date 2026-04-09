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


def _annotate_team(
    team: Dict[str, Any],
    *,
    anomaly_description: str,
    cost_spike_date: str,
    top_resources: List[Dict[str, Any]],
) -> None:
    team["anomaly_detected"] = True
    team["anomaly_description"] = anomaly_description
    team["cost_spike_date"] = cost_spike_date
    team["top_resources"] = copy.deepcopy(top_resources)

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
        "jobs": [
            {"job_id": "job-1", "name": "terraform-apply", "status": "success"},
            {
                "job_id": "job-1a",
                "name": "expiry-check",
                "status": "warning",
                "log_excerpt": "Environment created without confirmed teardown window; cleanup depends on destroy-loadtest.",
            },
        ]
    })
    
    for i, date in enumerate(("01-09", "01-10", "01-11")):
        pipes["pipelines"].append({
            "pipeline_id": f"pipe-fail-destroy-{i}",
            "name": "destroy-loadtest",
            "team_id": "ci-team",
            "status": "failed",
            "started_at": f"2025-{date}T23:00:00Z",
            "finished_at": f"2025-{date}T23:05:00Z",
            "jobs": [
                {
                    "job_id": f"job-d-{i}",
                    "name": "terraform-destroy",
                    "status": "failed",
                    "log_excerpt": "Error: Error acquiring the state lock while destroying the load-test environment.",
                }
            ]
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
        "resource_id": "res-loadtest-1", "name": "res-loadtest-1", "type": "vm",
        "tags": {"team": "ci-team", "env": "loadtest"}, "region": "eastus", "sku": "Standard",
        "daily_cost": [{"date": "2025-01-10", "cost": 200.0}], "created_at": "2025-01-09T10:00:00Z",
        "monthly_cost": 4200.0, "utilisation": 1.2, "status": "orphaned", "days_idle": 20,
        "reason_orphaned": "Load-test VM was never destroyed after repeated destroy-loadtest failures.",
        "metrics": "CPU utilization stayed below 2% after January 10, 2025."
    })
    ci_team["resources"].append({
        "resource_id": "res-loadtest-2", "name": "res-loadtest-2", "type": "vm",
        "tags": {"team": "ci-team", "env": "loadtest"}, "region": "eastus", "sku": "Standard",
        "daily_cost": [{"date": "2025-01-11", "cost": 195.0}], "created_at": "2025-01-09T10:00:00Z",
        "monthly_cost": 4095.0, "utilisation": 0.8, "status": "idle", "days_idle": 19,
        "metrics": "CPU utilization stayed below 1% after January 10, 2025."
    })

    _annotate_team(
        ci_team,
        anomaly_description="Load-test VMs res-loadtest-1 and res-loadtest-2 were not destroyed after failed destroy-loadtest runs.",
        cost_spike_date="2025-01-10",
        top_resources=[
            {"name": "res-loadtest-1", "type": "vm", "cost": 4200.0, "utilisation": 1.2},
            {"name": "res-loadtest-2", "type": "vm", "cost": 4095.0, "utilisation": 0.8},
        ],
    )
            
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
        "pipeline_id": "pipe-validate-rel-tags",
        "name": "validate-release-tags",
        "team_id": "release-team",
        "status": "failed",
        "started_at": "2025-01-14T09:30:00Z",
        "finished_at": "2025-01-14T09:35:00Z",
        "jobs": [
            {
                "job_id": "job-tag-check-1",
                "name": "tag-policy-check",
                "status": "failed",
                "log_excerpt": "Invalid ownership metadata detected: team=legacy on res-db-prod and missing team tag on res-api-1.",
            }
        ]
    })

    pipes["pipelines"].append({
        "pipeline_id": "pipe-deploy-rel",
        "name": "deploy-release-prod",
        "team_id": "release-team",
        "status": "success",
        "started_at": "2025-01-14T10:00:00Z",
        "finished_at": "2025-01-14T10:05:00Z",
        "jobs": [
            {"job_id": "job-1", "name": "terraform-apply", "status": "success", "log_excerpt": "Updating tags... team=legacy"},
            {
                "job_id": "job-2",
                "name": "tag-sync",
                "status": "success",
                "log_excerpt": "Applied tags to res-db-prod and res-api-1 with invalid ownership metadata.",
            },
        ]
    })
    
    rel_team["resources"].extend([
        {
            "resource_id": "res-db-prod", "name": "res-db-prod", "type": "db",
            "tags": {"team": "legacy"}, # Mistagged
            "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-14",
            "monthly_cost": 3100.0, "utilisation": 41.0, "status": "active",
            "metrics": "Database stayed active but its cost was attributed to an invalid team tag."
        },
        {
            "resource_id": "res-api-1", "name": "res-api-1", "type": "vm",
            "tags": {}, # Missing tag
            "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-14",
            "monthly_cost": 1450.0, "utilisation": 3.5, "status": "idle", "days_idle": 12,
            "metrics": "CPU utilization averaged 3.5% while the resource remained untagged."
        }
    ])

    _annotate_team(
        rel_team,
        anomaly_description="Release Team spend became unallocated because res-db-prod was tagged team=legacy and res-api-1 was missing team tags.",
        cost_spike_date="2025-01-15",
        top_resources=[
            {"name": "res-db-prod", "type": "db", "cost": 3100.0, "utilisation": 41.0},
            {"name": "res-api-1", "type": "vm", "cost": 1450.0, "utilisation": 3.5},
        ],
    )
    
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
        "pipeline_id": "pipe-validate-as",
        "name": "validate-web-autoscaler",
        "team_id": "release-team",
        "status": "failed",
        "started_at": "2025-01-09T09:15:00Z",
        "finished_at": "2025-01-09T09:20:00Z",
        "jobs": [
            {
                "job_id": "job-as-check",
                "name": "scale-down-guardrail-check",
                "status": "failed",
                "log_excerpt": "Scale-down guardrail failed: maxReplicas=12 with no valid scale-in metric threshold.",
            }
        ]
    })

    pipes["pipelines"].append({
        "pipeline_id": "pipe-update-as",
        "name": "update-web-autoscaler",
        "team_id": "release-team",
        "status": "success",
        "started_at": "2025-01-09T10:00:00Z",
        "finished_at": "2025-01-09T10:05:00Z",
        "jobs": [
            {"job_id": "job-1", "name": "deploy-config", "status": "success", "log_excerpt": "Updated HPA config limits"},
            {
                "job_id": "job-2",
                "name": "autoscaler-rollout",
                "status": "success",
                "log_excerpt": "Applied scale-out policy to web-frontend-asg with maxReplicas=12.",
            },
        ]
    })
    
    rel_team["resources"].append({
        "resource_id": "web-frontend-asg", "name": "web-frontend-asg", "type": "autoscaler",
        "tags": {"team": "release-team"}, "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-01",
        "monthly_cost": 5200.0, "utilisation": 94.0, "status": "active",
        "metrics": "Autoscaler changed from 4 to 12 instances on January 10, 2025 and never scaled back down."
    })
    
    rel_team["resources"].append({
        "resource_id": "res-web-frontend", "name": "res-web-frontend", "type": "vmss",
        "tags": {"team": "release-team"}, "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-01",
        "monthly_cost": 4700.0, "utilisation": 3.8, "status": "idle", "days_idle": 18,
        "metrics": "Scale set stayed over-provisioned with average CPU under 4% after January 10, 2025."
    })
    
    rel_team["resources"].append({
        "resource_id": "res-user-svc", "name": "user-service", "type": "vmss",
        "tags": {"team": "release-team"}, "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-01",
        "monthly_cost": 900.0, "utilisation": 56.0, "status": "active",
        "metrics": "Instance count: 2 -> 6 on Jan 10. Current: 2. Scaled back down OK."
    })

    _annotate_team(
        rel_team,
        anomaly_description="Autoscaler change left web-frontend-asg / res-web-frontend scaled out after January 10, 2025.",
        cost_spike_date="2025-01-10",
        top_resources=[
            {"name": "web-frontend-asg", "type": "autoscaler", "cost": 5200.0, "utilisation": 94.0},
            {"name": "res-web-frontend", "type": "vmss", "cost": 4700.0, "utilisation": 3.8},
        ],
    )
    
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
        "pipeline_id": "pipe-validate-poc-expiry",
        "name": "validate-poc-expiry",
        "team_id": "cloudops-team",
        "status": "failed",
        "started_at": "2025-01-14T09:40:00Z",
        "finished_at": "2025-01-14T09:45:00Z",
        "jobs": [
            {
                "job_id": "job-poc-expiry-check",
                "name": "ttl-policy-check",
                "status": "failed",
                "log_excerpt": "Missing expiration tag on poc-analytics resources; automatic cleanup will not run.",
            }
        ]
    })

    pipes["pipelines"].append({
        "pipeline_id": "pipe-deploy-poc",
        "name": "deploy-poc-analytics",
        "team_id": "cloudops-team",
        "status": "success",
        "started_at": "2025-01-14T10:00:00Z",
        "finished_at": "2025-01-14T10:05:00Z",
        "jobs": [
            {"job_id": "job-1", "name": "terraform-apply", "status": "success"},
            {
                "job_id": "job-2",
                "name": "notify-owner",
                "status": "warning",
                "log_excerpt": "No owner confirmed for poc-analytics cleanup after project end date.",
            },
        ]
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
            "monthly_cost": 3600.0, "utilisation": 0.4, "status": "idle", "days_idle": 16,
            "metrics": "CPU utilization: ~0% after Jan 15"
        },
        {
            "resource_id": "poc-analytics-db", "name": "poc-analytics-db", "type": "db",
            "tags": {"env": "test", "project": "poc-analytics", "team": "cloudops-team"},
            "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-14",
            "monthly_cost": 1800.0, "utilisation": 1.1, "status": "idle", "days_idle": 16,
            "metrics": "Database connections stayed near zero after January 15, 2025."
        }
    ])

    _annotate_team(
        ops_team,
        anomaly_description="POC analytics resources poc-analytics-vm-1 and poc-analytics-db were never cleaned up and stayed idle after January 15, 2025.",
        cost_spike_date="2025-01-15",
        top_resources=[
            {"name": "poc-analytics-vm-1", "type": "vm", "cost": 3600.0, "utilisation": 0.4},
            {"name": "poc-analytics-db", "type": "db", "cost": 1800.0, "utilisation": 1.1},
        ],
    )
    
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
        "pipeline_id": "pipe-validate-rel-api-config",
        "name": "validate-release-api-config",
        "team_id": "release-team",
        "status": "failed",
        "started_at": "2025-01-19T09:30:00Z",
        "finished_at": "2025-01-19T09:35:00Z",
        "jobs": [
            {
                "job_id": "job-config-lint",
                "name": "config-lint",
                "status": "failed",
                "log_excerpt": "MAX_WORKERS=500 exceeds approved production limit of 64.",
            }
        ]
    })

    pipes["pipelines"].append({
        "pipeline_id": "pipe-deploy-rel-api",
        "name": "deploy-release-api",
        "team_id": "release-team",
        "status": "success",
        "started_at": "2025-01-19T10:00:00Z",
        "finished_at": "2025-01-19T10:05:00Z",
        "jobs": [
            {"job_id": "job-1", "name": "deploy-k8s", "status": "success", "log_excerpt": "Config update: MAX_WORKERS=500"},
            {
                "job_id": "job-2",
                "name": "post-deploy-canary",
                "status": "warning",
                "log_excerpt": "Canary saw retry storm risk after worker-count increase, but rollout continued.",
            },
        ]
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
            "resource_id": "release-api", "name": "release-api", "type": "service",
            "tags": {"team": "release-team"},
            "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-01",
            "monthly_cost": 5400.0, "utilisation": 88.0, "status": "active",
            "metrics": "Application rollout introduced MAX_WORKERS=500 and sustained retry storms."
    })

    rel_team["resources"].append({
            "resource_id": "rel-api-pods", "name": "rel-api-pods", "type": "k8s-pod-set",
            "tags": {"team": "release-team"},
            "region": "eastus", "sku": "Standard", "daily_cost": [], "created_at": "2025-01-19",
            "monthly_cost": 6200.0, "utilisation": 2.4, "status": "idle", "days_idle": 11,
            "metrics": "Pod count jump from 5 to 50 on Jan 19. Repeated app logs 'failed to process message, retrying'."
    })

    _annotate_team(
        rel_team,
        anomaly_description="MAX_WORKERS=500 in deploy-release-api caused release-api / rel-api-pods to scale far beyond normal demand.",
        cost_spike_date="2025-01-20",
        top_resources=[
            {"name": "release-api", "type": "service", "cost": 5400.0, "utilisation": 88.0},
            {"name": "rel-api-pods", "type": "k8s-pod-set", "cost": 6200.0, "utilisation": 2.4},
        ],
    )
    
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
