"""GitLab CI/CD pipeline provider using GitLab API."""

import os
import re
import logging
from datetime import datetime, timedelta
from typing import List, Optional
import requests
from .base_pipeline_provider import PipelineDataProvider

logger = logging.getLogger(__name__)


# Team to GitLab project mapping
TEAM_PROJECT_CONFIG = {
    "release-team": {
        "display_name": "Release Team",
        "project_id": os.getenv("GITLAB_PROJECT_ID_RELEASE"),
        "project_path": "your-group/release-infrastructure",
        "lead": "Alex Johnson"
    },
    "ci-team": {
        "display_name": "CI Team",
        "project_id": os.getenv("GITLAB_PROJECT_ID_CI"),
        "project_path": "your-group/ci-infrastructure",
        "lead": "James Wilson"
    },
    "cloudops-team": {
        "display_name": "CloudOps Team",
        "project_id": os.getenv("GITLAB_PROJECT_ID_CLOUDOPS"),
        "project_path": "your-group/cloudops-infrastructure",
        "lead": "David Brown"
    }
}

# For single project setup (all teams in one repo)
SINGLE_PROJECT_MODE = os.getenv("GITLAB_SINGLE_PROJECT", "true").lower() == "true"


class GitLabPipelineProvider(PipelineDataProvider):
    """GitLab CI/CD pipeline provider."""
    
    def __init__(self):
        self.gitlab_url = os.getenv("GITLAB_URL", "https://gitlab.com")
        self.token = os.getenv("GITLAB_TOKEN", "")
        self.project_id = os.getenv("GITLAB_PROJECT_ID", "")
        self.teams = TEAM_PROJECT_CONFIG
        self._session = None
    
    @property
    def provider_name(self) -> str:
        return "gitlab"
    
    @property
    def session(self) -> requests.Session:
        """Get or create requests session with auth headers."""
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "PRIVATE-TOKEN": self.token,
                "Content-Type": "application/json"
            })
        return self._session
    
    def is_available(self) -> bool:
        """Check if GitLab API is accessible."""
        if not self.token:
            logger.warning("GITLAB_TOKEN not set")
            return False
        if not self.project_id:
            logger.warning("GITLAB_PROJECT_ID not set")
            return False
        
        try:
            response = self.session.get(
                f"{self.gitlab_url}/api/v4/projects/{self.project_id}",
                timeout=10
            )
            if response.status_code == 200:
                logger.info("✅ GitLab API connection successful")
                return True
            else:
                logger.warning(f"GitLab API returned {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"GitLab API error: {e}")
            return False
    
    def get_team_keys(self) -> List[str]:
        return list(self.teams.keys())
    
    def _normalize_team_name(self, team_name: str) -> str:
        return team_name.lower().replace(" ", "-").replace("_", "-")
    
    def _get_project_id(self, team_name: str) -> str:
        """Get GitLab project ID for a team."""
        if SINGLE_PROJECT_MODE:
            return self.project_id
        
        normalized = self._normalize_team_name(team_name)
        team = self.teams.get(normalized, {})
        return team.get("project_id", self.project_id)
    
    def get_pipelines(self, team_name: str, days: int = 7) -> dict:
        """Get recent pipelines from GitLab API."""
        normalized = self._normalize_team_name(team_name)
        
        if normalized not in self.teams:
            return {
                "success": False,
                "error": f"Team '{team_name}' not found. Available: {', '.join(self.teams.keys())}"
            }
        
        team = self.teams[normalized]
        project_id = self._get_project_id(team_name)
        
        try:
            # Calculate date range
            updated_after = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Get pipelines from GitLab API
            response = self.session.get(
                f"{self.gitlab_url}/api/v4/projects/{project_id}/pipelines",
                params={
                    "updated_after": updated_after,
                    "per_page": 20,
                    "order_by": "updated_at",
                    "sort": "desc"
                },
                timeout=30
            )
            response.raise_for_status()
            
            pipelines_raw = response.json()
            
            # Get detailed info for each pipeline
            pipelines = []
            for p in pipelines_raw[:10]:  # Limit to 10 for performance
                # Get pipeline details
                detail_resp = self.session.get(
                    f"{self.gitlab_url}/api/v4/projects/{project_id}/pipelines/{p['id']}",
                    timeout=30
                )
                if detail_resp.status_code == 200:
                    detail = detail_resp.json()
                    
                    # Get jobs for this pipeline
                    jobs_resp = self.session.get(
                        f"{self.gitlab_url}/api/v4/projects/{project_id}/pipelines/{p['id']}/jobs",
                        timeout=30
                    )
                    jobs = jobs_resp.json() if jobs_resp.status_code == 200 else []
                    
                    pipelines.append({
                        "id": p["id"],
                        "status": p["status"],
                        "source": p.get("source", "unknown"),
                        "ref": p["ref"],
                        "created_at": p["created_at"],
                        "finished_at": detail.get("finished_at"),
                        "duration": detail.get("duration", 0),
                        "commit_message": detail.get("commit", {}).get("title", ""),
                        "commit_author": detail.get("user", {}).get("username", "unknown"),
                        "stages": list(set(j.get("stage", "") for j in jobs)),
                        "jobs": [
                            {
                                "id": j["id"],
                                "name": j["name"],
                                "status": j["status"],
                                "duration": j.get("duration", 0)
                            }
                            for j in jobs
                        ]
                    })
            
            # Calculate statistics
            total = len(pipelines)
            success = len([p for p in pipelines if p["status"] == "success"])
            failed = len([p for p in pipelines if p["status"] == "failed"])
            
            return {
                "success": True,
                "team": team["display_name"],
                "project": f"{self.gitlab_url}/{project_id}",
                "project_id": project_id,
                "period": f"Last {days} days",
                "retrieved_at": datetime.now().isoformat(),
                "statistics": {
                    "total_pipelines": total,
                    "successful": success,
                    "failed": failed,
                    "success_rate": f"{(success/max(total,1))*100:.1f}%"
                },
                "pipelines": pipelines,
                "data_source": "gitlab"
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GitLab API error: {e}")
            return {"success": False, "error": f"GitLab API error: {str(e)}"}
        except Exception as e:
            logger.error(f"Error fetching pipelines: {e}")
            return {"success": False, "error": str(e)}
    
    def get_pipeline_details(self, pipeline_id: int) -> dict:
        """Get detailed information about a specific pipeline."""
        project_id = self.project_id
        
        try:
            # Get pipeline details
            response = self.session.get(
                f"{self.gitlab_url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}",
                timeout=30
            )
            response.raise_for_status()
            pipeline = response.json()
            
            # Get jobs
            jobs_resp = self.session.get(
                f"{self.gitlab_url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs",
                timeout=30
            )
            jobs = jobs_resp.json() if jobs_resp.status_code == 200 else []
            
            return {
                "success": True,
                "pipeline": {
                    "id": pipeline["id"],
                    "status": pipeline["status"],
                    "ref": pipeline["ref"],
                    "created_at": pipeline["created_at"],
                    "finished_at": pipeline.get("finished_at"),
                    "duration": pipeline.get("duration", 0),
                    "web_url": pipeline.get("web_url"),
                    "jobs": [
                        {
                            "id": j["id"],
                            "name": j["name"],
                            "stage": j.get("stage"),
                            "status": j["status"],
                            "duration": j.get("duration", 0),
                            "web_url": j.get("web_url")
                        }
                        for j in jobs
                    ]
                }
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_job_logs(self, pipeline_id: int, job_name: str) -> dict:
        """Get logs for a specific job."""
        project_id = self.project_id
        
        try:
            # First get jobs to find the job ID
            jobs_resp = self.session.get(
                f"{self.gitlab_url}/api/v4/projects/{project_id}/pipelines/{pipeline_id}/jobs",
                timeout=30
            )
            jobs_resp.raise_for_status()
            jobs = jobs_resp.json()
            
            # Find the job by name
            job = next((j for j in jobs if j["name"] == job_name), None)
            if not job:
                return {"success": False, "error": f"Job '{job_name}' not found in pipeline {pipeline_id}"}
            
            # Get job trace (logs)
            trace_resp = self.session.get(
                f"{self.gitlab_url}/api/v4/projects/{project_id}/jobs/{job['id']}/trace",
                timeout=60
            )
            
            if trace_resp.status_code == 200:
                logs = trace_resp.text
            else:
                logs = f"[Could not retrieve logs: {trace_resp.status_code}]"
            
            return {
                "success": True,
                "pipeline_id": pipeline_id,
                "job_name": job_name,
                "job_id": job["id"],
                "status": job["status"],
                "logs": logs
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_infrastructure_changes(self, team_name: str, days: int = 7) -> dict:
        """Extract infrastructure changes from pipeline logs."""
        # Get recent pipelines
        pipelines_result = self.get_pipelines(team_name, days)
        if not pipelines_result["success"]:
            return pipelines_result
        
        changes = []
        
        # Look for terraform/infrastructure jobs in successful pipelines
        for pipeline in pipelines_result["pipelines"]:
            if pipeline["status"] != "success":
                continue
            
            infra_jobs = [
                j for j in pipeline["jobs"]
                if any(kw in j["name"].lower() for kw in ["apply", "scale", "terraform", "deploy", "provision"])
            ]
            
            for job in infra_jobs:
                # Get job logs and parse for INFRA_CHANGE markers
                logs_result = self.get_job_logs(pipeline["id"], job["name"])
                if logs_result["success"]:
                    # Parse logs for infrastructure change markers
                    parsed_changes = self._parse_infra_changes(logs_result["logs"], pipeline)
                    changes.extend(parsed_changes)
        
        # Calculate total cost impact
        total_cost_change = sum(c.get("estimated_monthly_cost_change", 0) for c in changes)
        
        return {
            "success": True,
            "team": pipelines_result["team"],
            "period": f"Last {days} days",
            "changes": changes,
            "total_cost_impact": f"${total_cost_change:,.2f}/month",
            "change_count": len(changes)
        }
    
    def _parse_infra_changes(self, logs: str, pipeline: dict) -> List[dict]:
        """Parse infrastructure changes from job logs."""
        changes = []
        
        # Look for INFRA_CHANGE markers in logs
        # Format: INFRA_CHANGE: <timestamp> | ACTION: <action> | ...
        pattern = r"INFRA_CHANGE:\s*([^|]+)\s*\|\s*ACTION:\s*(\w+)(?:\s*\|\s*(.+))?"
        
        for match in re.finditer(pattern, logs):
            timestamp = match.group(1).strip()
            action = match.group(2).strip()
            extra = match.group(3) or ""
            
            # Parse extra fields
            extra_fields = {}
            for field in extra.split("|"):
                if ":" in field:
                    key, value = field.split(":", 1)
                    extra_fields[key.strip().lower()] = value.strip()
            
            # Estimate cost change based on action
            cost_change = 0
            if "est_cost_change" in extra_fields:
                cost_str = extra_fields["est_cost_change"]
                cost_match = re.search(r"([+-]?\$?[\d.]+)", cost_str)
                if cost_match:
                    cost_change = float(cost_match.group(1).replace("$", "").replace("+", ""))
            elif action == "scale_up":
                cost_change = 5.0
            elif action == "scale_down":
                cost_change = -3.0
            elif action == "destroy":
                cost_change = -15.0
            
            changes.append({
                "date": timestamp,
                "pipeline_id": pipeline["id"],
                "type": action.upper(),
                "description": f"{action.replace('_', ' ').title()} from pipeline #{pipeline['id']}",
                "resources_affected": extra_fields.get("resources", "").split(",") if extra_fields.get("resources") else [],
                "estimated_monthly_cost_change": cost_change,
                "triggered_by": pipeline.get("commit_author", "unknown"),
                "status": extra_fields.get("status", "success")
            })
        
        return changes
    
    def trigger_pipeline(self, team_name: str, action: str, variables: dict = None) -> dict:
        """Trigger a new pipeline with specified action."""
        project_id = self._get_project_id(team_name)
        
        # Prepare pipeline variables
        pipeline_vars = {"ACTION": action}
        if variables:
            pipeline_vars.update(variables)
        
        try:
            response = self.session.post(
                f"{self.gitlab_url}/api/v4/projects/{project_id}/pipeline",
                json={
                    "ref": "main",
                    "variables": [
                        {"key": k, "value": v}
                        for k, v in pipeline_vars.items()
                    ]
                },
                timeout=30
            )
            response.raise_for_status()
            pipeline = response.json()
            
            return {
                "success": True,
                "message": f"Pipeline triggered successfully",
                "action": action,
                "variables": pipeline_vars,
                "pipeline_id": pipeline["id"],
                "web_url": pipeline.get("web_url"),
                "status": pipeline["status"]
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}