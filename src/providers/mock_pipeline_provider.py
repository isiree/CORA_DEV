"""Mock pipeline data provider for demo/testing."""

from datetime import datetime, timedelta
from typing import List, Optional
from .base_pipeline_provider import PipelineDataProvider


# Mock data simulating GitLab CI/CD
MOCK_PIPELINE_DATA = {
    "release-team": {
        "display_name": "Release Team",
        "project_id": 12345,
        "project_name": "abc-release-pipeline",
        "project_path": "abc-company/release-pipeline",
        "pipelines": [
            {
                "id": 98765,
                "status": "success",
                "source": "push",
                "ref": "main",
                "created_at": (datetime.now() - timedelta(hours=2)).isoformat(),
                "finished_at": (datetime.now() - timedelta(hours=1, minutes=45)).isoformat(),
                "duration": 900,
                "commit_message": "Deploy new API gateway configuration",
                "commit_author": "alex.johnson@abc.com",
                "stages": ["validate", "plan", "apply"],
                "jobs": [
                    {"id": 1001, "name": "validate", "status": "success", "duration": 45},
                    {"id": 1002, "name": "plan", "status": "success", "duration": 120},
                    {"id": 1003, "name": "apply", "status": "success", "duration": 340}
                ]
            },
            {
                "id": 98760,
                "status": "success",
                "source": "trigger",
                "ref": "main",
                "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
                "finished_at": (datetime.now() - timedelta(days=1) + timedelta(minutes=35)).isoformat(),
                "duration": 2100,
                "commit_message": "Scale up release infrastructure - add 3 new VMs",
                "commit_author": "alex.johnson@abc.com",
                "stages": ["validate", "plan", "scale_up"],
                "jobs": [
                    {"id": 1004, "name": "validate", "status": "success", "duration": 60},
                    {"id": 1005, "name": "plan", "status": "success", "duration": 180},
                    {"id": 1006, "name": "scale_up", "status": "success", "duration": 890}
                ]
            },
            {
                "id": 98755,
                "status": "failed",
                "source": "push",
                "ref": "feature/cost-optimization",
                "created_at": (datetime.now() - timedelta(days=3)).isoformat(),
                "finished_at": (datetime.now() - timedelta(days=3) + timedelta(minutes=15)).isoformat(),
                "duration": 900,
                "commit_message": "Attempt to reduce container resources",
                "commit_author": "alex.johnson@abc.com",
                "stages": ["validate", "plan", "apply"],
                "jobs": [
                    {"id": 1007, "name": "validate", "status": "success", "duration": 45},
                    {"id": 1008, "name": "plan", "status": "success", "duration": 120},
                    {"id": 1009, "name": "apply", "status": "failed", "duration": 200}
                ]
            }
        ],
        "infrastructure_changes": [
            {
                "date": (datetime.now() - timedelta(days=1)).isoformat(),
                "pipeline_id": 98760,
                "type": "SCALE_UP",
                "description": "Provisioned 3 new D4s_v3 VMs for release pipeline scaling",
                "resources_affected": ["azurerm_virtual_machine.release[0-2]"],
                "estimated_monthly_cost_change": 450.00,
                "triggered_by": "alex.johnson@abc.com"
            },
            {
                "date": (datetime.now() - timedelta(days=7)).isoformat(),
                "pipeline_id": 98700,
                "type": "STORAGE_INCREASE",
                "description": "Increased blob storage from 500GB to 1TB",
                "resources_affected": ["azurerm_storage_account.release"],
                "estimated_monthly_cost_change": 50.00,
                "triggered_by": "manual"
            }
        ]
    },
    "ci-team": {
        "display_name": "CI Team",
        "project_id": 12346,
        "project_name": "abc-ci-infrastructure",
        "project_path": "abc-company/ci-infrastructure",
        "pipelines": [
            {
                "id": 87654,
                "status": "success",
                "source": "push",
                "ref": "main",
                "created_at": (datetime.now() - timedelta(hours=6)).isoformat(),
                "finished_at": (datetime.now() - timedelta(hours=5, minutes=50)).isoformat(),
                "duration": 600,
                "commit_message": "Optimize build cache configuration",
                "commit_author": "james.wilson@abc.com",
                "stages": ["validate", "apply"],
                "jobs": [
                    {"id": 2001, "name": "validate", "status": "success", "duration": 30},
                    {"id": 2002, "name": "apply", "status": "success", "duration": 230}
                ]
            }
        ],
        "infrastructure_changes": []
    },
    "cloudops-team": {
        "display_name": "CloudOps Team",
        "project_id": 12347,
        "project_name": "abc-cloudops-infrastructure",
        "project_path": "abc-company/cloudops-infrastructure",
        "pipelines": [
            {
                "id": 76543,
                "status": "success",
                "source": "schedule",
                "ref": "main",
                "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
                "finished_at": (datetime.now() - timedelta(days=2) + timedelta(hours=1)).isoformat(),
                "duration": 3600,
                "commit_message": "DR failover test - temporary resource scaling",
                "commit_author": "system",
                "stages": ["prepare", "failover", "validate", "restore"],
                "jobs": [
                    {"id": 3001, "name": "scale-dr-region", "status": "success", "duration": 1200},
                    {"id": 3002, "name": "failover-test", "status": "success", "duration": 800},
                    {"id": 3003, "name": "validate", "status": "success", "duration": 600},
                    {"id": 3004, "name": "scale-down", "status": "success", "duration": 600}
                ]
            }
        ],
        "infrastructure_changes": [
            {
                "date": (datetime.now() - timedelta(days=2)).isoformat(),
                "pipeline_id": 76543,
                "type": "DR_TEST",
                "description": "Temporary DR region scaling for failover test",
                "resources_affected": ["azurerm_virtual_machine.dr[*]"],
                "estimated_monthly_cost_change": 0,
                "triggered_by": "scheduled"
            }
        ]
    }
}

# Mock job logs
MOCK_JOB_LOGS = {
    1003: """
[2026-02-04 10:15:32] Starting terraform apply...
[2026-02-04 10:15:33] azurerm_resource_group.main: Refreshing state...
[2026-02-04 10:15:35] azurerm_storage_account.release: Creating...
[2026-02-04 10:16:45] azurerm_storage_account.release: Creation complete after 70s
[2026-02-04 10:16:46] INFRA_CHANGE: 2026-02-04T10:16:46+00:00 | ACTION: apply | STATUS: success
[2026-02-04 10:20:32] Apply complete! Resources: 3 added, 0 changed, 0 destroyed.
[2026-02-04 10:20:33] ✅ Infrastructure deployed successfully
""",
    1006: """
[2026-02-03 14:30:00] Starting scale_up operation...
[2026-02-03 14:30:01] Current configuration: container_cpu=0.25, container_memory=0.5
[2026-02-03 14:30:02] Target configuration: container_cpu=0.5, container_memory=1.0
[2026-02-03 14:30:05] azurerm_container_group.ci: Modifying...
[2026-02-03 14:35:20] azurerm_container_group.ci: Modifications complete after 315s
[2026-02-03 14:35:21] INFRA_CHANGE: 2026-02-03T14:35:21+00:00 | ACTION: scale_up | RESOURCES: container_cpu=0.5,container_memory=1.0 | EST_COST_CHANGE: +$5/month
[2026-02-03 14:35:22] ✅ Scale up completed
""",
    1009: """
[2026-02-01 09:00:00] Starting terraform apply...
[2026-02-01 09:00:15] azurerm_container_group.ci: Modifying...
[2026-02-01 09:03:20] Error: insufficient quota for requested resources
[2026-02-01 09:03:21] ❌ Apply failed - rolling back changes
[2026-02-01 09:03:22] INFRA_CHANGE: 2026-02-01T09:03:22+00:00 | ACTION: apply | STATUS: failed | ERROR: quota_exceeded
"""
}


class MockPipelineDataProvider(PipelineDataProvider):
    """Mock pipeline provider for demo/testing."""
    
    def __init__(self):
        self.teams = MOCK_PIPELINE_DATA
    
    @property
    def provider_name(self) -> str:
        return "mock"
    
    def is_available(self) -> bool:
        return True
    
    def get_team_keys(self) -> List[str]:
        return list(self.teams.keys())
    
    def _normalize_team_name(self, team_name: str) -> str:
        return team_name.lower().replace(" ", "-").replace("_", "-")
    
    def get_pipelines(self, team_name: str, days: int = 7) -> dict:
        normalized = self._normalize_team_name(team_name)
        
        if normalized not in self.teams:
            return {
                "success": False,
                "error": f"Team '{team_name}' not found. Available: {', '.join(self.teams.keys())}"
            }
        
        team = self.teams[normalized]
        cutoff = datetime.now() - timedelta(days=days)
        
        # Filter pipelines by date
        recent_pipelines = [
            p for p in team["pipelines"]
            if datetime.fromisoformat(p["created_at"].replace("Z", "+00:00").replace("+00:00", "")) > cutoff
        ]
        
        # Calculate statistics
        total = len(recent_pipelines)
        success = len([p for p in recent_pipelines if p["status"] == "success"])
        failed = len([p for p in recent_pipelines if p["status"] == "failed"])
        
        return {
            "success": True,
            "team": team["display_name"],
            "project": team["project_name"],
            "project_path": team["project_path"],
            "period": f"Last {days} days",
            "retrieved_at": datetime.now().isoformat(),
            "statistics": {
                "total_pipelines": total,
                "successful": success,
                "failed": failed,
                "success_rate": f"{(success/max(total,1))*100:.1f}%"
            },
            "pipelines": recent_pipelines,
            "data_source": "mock"
        }
    
    def get_pipeline_details(self, pipeline_id: int) -> dict:
        # Search for pipeline across all teams
        for team_key, team in self.teams.items():
            for pipeline in team["pipelines"]:
                if pipeline["id"] == pipeline_id:
                    return {
                        "success": True,
                        "pipeline": pipeline,
                        "team": team["display_name"],
                        "project": team["project_name"]
                    }
        
        return {"success": False, "error": f"Pipeline {pipeline_id} not found"}
    
    def get_job_logs(self, pipeline_id: int, job_name: str) -> dict:
        # Find the job
        for team in self.teams.values():
            for pipeline in team["pipelines"]:
                if pipeline["id"] == pipeline_id:
                    for job in pipeline["jobs"]:
                        if job["name"] == job_name:
                            logs = MOCK_JOB_LOGS.get(job["id"], f"[No logs available for job {job['id']}]")
                            return {
                                "success": True,
                                "pipeline_id": pipeline_id,
                                "job_name": job_name,
                                "job_id": job["id"],
                                "status": job["status"],
                                "logs": logs
                            }
                    return {"success": False, "error": f"Job '{job_name}' not found in pipeline {pipeline_id}"}
        
        return {"success": False, "error": f"Pipeline {pipeline_id} not found"}
    
    def get_infrastructure_changes(self, team_name: str, days: int = 7) -> dict:
        normalized = self._normalize_team_name(team_name)
        
        if normalized not in self.teams:
            return {
                "success": False,
                "error": f"Team '{team_name}' not found"
            }
        
        team = self.teams[normalized]
        changes = team.get("infrastructure_changes", [])
        
        # Calculate total cost impact
        total_cost_change = sum(c.get("estimated_monthly_cost_change", 0) for c in changes)
        
        return {
            "success": True,
            "team": team["display_name"],
            "period": f"Last {days} days",
            "changes": changes,
            "total_cost_impact": f"${total_cost_change:,.2f}/month",
            "change_count": len(changes)
        }
    
    def trigger_pipeline(self, team_name: str, action: str, variables: dict = None) -> dict:
        """Mock pipeline trigger - just returns simulated response."""
        normalized = self._normalize_team_name(team_name)
        
        if normalized not in self.teams:
            return {"success": False, "error": f"Team '{team_name}' not found"}
        
        team = self.teams[normalized]
        
        return {
            "success": True,
            "message": f"[MOCK] Pipeline triggered for {team['display_name']}",
            "action": action,
            "variables": variables or {},
            "pipeline_id": 99999,
            "web_url": f"https://gitlab.com/{team['project_path']}/-/pipelines/99999",
            "note": "This is a mock response. In live mode, this would trigger a real GitLab pipeline."
        }