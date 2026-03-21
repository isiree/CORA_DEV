"""
Pipeline Tool - GitLab CI/CD pipeline analysis.

Analyzes deployment history, infrastructure changes, and pipeline activity
to correlate with cost changes. Uses LLM to extract insights from logs.

Supports both live GitLab API and mock data based on USE_LIVE_DATA setting.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

from ..utils.cache_manager import get_cache
from ..providers import is_gitlab_live_mode, get_pipeline_provider
from ..g import g

load_dotenv()


def _is_mock_mode() -> bool:
    return not is_gitlab_live_mode()


# Mock GitLab pipeline data for demo
MOCK_PIPELINE_DATA = {
    "release-team": {
        "team": "Release Team",
        "project": "abc-release-pipeline",
        "recent_pipelines": [
            {
                "id": 12345,
                "status": "success",
                "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
                "duration_seconds": 1245,
                "ref": "main",
                "commit_message": "Deploy new API gateway configuration",
                "stages": ["build", "test", "deploy-staging", "deploy-prod"],
                "jobs": [
                    {"name": "terraform-apply", "status": "success", "duration": 340},
                    {"name": "deploy-k8s", "status": "success", "duration": 180}
                ]
            },
            {
                "id": 12340,
                "status": "success",
                "created_at": (datetime.now() - timedelta(days=3)).isoformat(),
                "duration_seconds": 2100,
                "ref": "main",
                "commit_message": "Scale up release infrastructure - add 3 new VMs",
                "stages": ["build", "test", "infra-provision", "deploy-prod"],
                "jobs": [
                    {"name": "terraform-apply", "status": "success", "duration": 890},
                    {"name": "vm-provisioning", "status": "success", "duration": 450},
                    {"name": "deploy-k8s", "status": "success", "duration": 200}
                ]
            },
            {
                "id": 12335,
                "status": "success",
                "created_at": (datetime.now() - timedelta(days=5)).isoformat(),
                "duration_seconds": 980,
                "ref": "main",
                "commit_message": "Update monitoring dashboards",
                "stages": ["build", "deploy"],
                "jobs": [
                    {"name": "deploy-grafana", "status": "success", "duration": 120}
                ]
            }
        ],
        "infrastructure_changes": [
            {
                "date": (datetime.now() - timedelta(days=3)).isoformat(),
                "type": "VM_PROVISIONING",
                "description": "Provisioned 3 new D4s_v3 VMs for release pipeline scaling",
                "estimated_monthly_cost": 450,
                "triggered_by": "pipeline-12340"
            },
            {
                "date": (datetime.now() - timedelta(days=7)).isoformat(),
                "type": "STORAGE_INCREASE",
                "description": "Increased blob storage from 500GB to 1TB",
                "estimated_monthly_cost": 50,
                "triggered_by": "manual"
            }
        ],
        "deployment_count_7_days": 12,
        "failed_deployments_7_days": 1,
        "rollbacks_7_days": 0
    },
    "ci-team": {
        "team": "CI Team",
        "project": "abc-ci-infrastructure",
        "recent_pipelines": [
            {
                "id": 45678,
                "status": "success",
                "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
                "duration_seconds": 890,
                "ref": "main",
                "commit_message": "Optimize build cache configuration",
                "stages": ["build", "test"],
                "jobs": [
                    {"name": "update-cache", "status": "success", "duration": 230}
                ]
            }
        ],
        "infrastructure_changes": [],
        "deployment_count_7_days": 8,
        "failed_deployments_7_days": 0,
        "rollbacks_7_days": 0
    },
    "cloudops-team": {
        "team": "CloudOps Team",
        "project": "abc-infrastructure",
        "recent_pipelines": [
            {
                "id": 78901,
                "status": "success",
                "created_at": (datetime.now() - timedelta(days=2)).isoformat(),
                "duration_seconds": 3400,
                "ref": "main",
                "commit_message": "DR failover test - temporary resource scaling",
                "stages": ["prepare", "failover", "validate", "restore"],
                "jobs": [
                    {"name": "scale-dr-region", "status": "success", "duration": 1200},
                    {"name": "failover-test", "status": "success", "duration": 800},
                    {"name": "scale-down", "status": "success", "duration": 600}
                ]
            }
        ],
        "infrastructure_changes": [
            {
                "date": (datetime.now() - timedelta(days=2)).isoformat(),
                "type": "DR_TEST",
                "description": "Temporary DR region scaling for failover test",
                "estimated_monthly_cost": 0,  # Temporary
                "triggered_by": "pipeline-78901"
            }
        ],
        "deployment_count_7_days": 5,
        "failed_deployments_7_days": 0,
        "rollbacks_7_days": 0
    }
}


class PipelineTool:
    """
    Tool for analyzing GitLab CI/CD pipelines and correlating with cost data.
    
    Supports both live GitLab API and mock data based on USE_LIVE_DATA setting.
    """
    
    def __init__(self, llm: Optional[ChatGroq] = None):
        self.cache = get_cache()
        self.cache_ttl = 300  # 5 minutes
        self.llm = llm or ChatGroq(
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            temperature=0
        )
        
        self.analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a DevOps analyst specializing in CI/CD pipeline analysis and cost correlation.
Analyze the pipeline data and infrastructure changes to identify:
1. Activities that may have caused cost increases
2. Resource provisioning events
3. Deployment patterns that affect spending
4. Recommendations for cost optimization

Be specific about dates, resources, and estimated costs when available."""),
            ("human", """Analyze this pipeline data for {team_name}:

Pipeline Activity (Last 7 Days):
{pipeline_summary}

Infrastructure Changes:
{infra_changes}

Deployment Statistics:
- Total deployments: {deployment_count}
- Failed deployments: {failed_count}
- Rollbacks: {rollback_count}

Provide analysis focused on cost impact:""")
        ])
    
    def _is_live_mode(self) -> bool:
        """Check if using live GitLab API or mock data."""
        return is_gitlab_live_mode()
    
    def _get_mode_indicator(self) -> str:
        """Get the mode indicator string for output."""
        if self._is_live_mode():
            return "LIVE 🟢"
        return "MOCK 🟡"
    
    def _normalize_team_name(self, team_name: str) -> str:
        """Normalize team name for lookup."""
        return team_name.lower().replace(" ", "-").replace("_", "-")
    
    def _get_live_data(self, team_name: str, days: int = 7) -> dict:
        """
        Fetch live data from GitLab API.
        """
        if _is_mock_mode():
            return self._get_mock_data(team_name, days)

        try:
            provider = get_pipeline_provider()
            normalized_team = self._normalize_team_name(team_name)
            result = provider.get_pipelines(team_name=normalized_team, days=days)
            
            if not result.get("success", False):
                return result
            
            pipelines = result.get("pipelines", [])
            stats = result.get("statistics", {})
            
            return {
                "success": True,
                "team": result.get("team", team_name),
                "project": result.get("project", f"GitLab Project {os.getenv('GITLAB_PROJECT_ID', 'Unknown')}"),
                "period": result.get("period", f"Last {days} days"),
                "retrieved_at": result.get("retrieved_at", datetime.now().isoformat()),
                "statistics": {
                    "total_deployments": stats.get("total_pipelines", len(pipelines)),
                    "failed_deployments": stats.get("failed", 0),
                    "rollbacks": 0,
                    "success_rate": stats.get("success_rate", "0%")
                },
                "recent_pipelines": [
                    {
                        "id": p.get("id"),
                        "status": p.get("status"),
                        "created_at": p.get("created_at"),
                        "duration_seconds": p.get("duration", 0),
                        "ref": p.get("ref"),
                        "commit_message": p.get("commit_message", "No message"),
                        "stages": p.get("stages", []),
                        "jobs": p.get("jobs", [])
                    }
                    for p in pipelines[:10]
                ],
                "infrastructure_changes": []
            }
        except Exception as e:
            if _is_mock_mode():
                msg = "Mock data unavailable for this query. Ensure a scenario is selected."
            else:
                msg = f"Failed to fetch live GitLab data: {str(e)}"
            return {
                "success": False,
                "error": msg
            }
    
    def _get_mock_data(self, team_name: str, days: int = 7) -> dict:
        """
        Get mock data for demo purposes.
        
        Args:
            team_name: Name of the team
            days: Number of days to look back
        
        Returns:
            Dictionary with mock pipeline data
        """
        normalized_name = self._normalize_team_name(team_name)
        scenario_run = getattr(g, 'scenario_run', None)
        
        if scenario_run is not None and getattr(scenario_run, 'pipeline_data', None):
            # Extract from scenario
            pipes = scenario_run.pipeline_data.get("pipelines", [])
            team_pipes = [p for p in pipes if p.get("team_id") == normalized_name]
            
            # Simple stats
            failed = len([p for p in team_pipes if p.get("status") == "failed"])
            total = len(team_pipes)
            success_rate = f"{((total - failed) / max(total, 1)) * 100:.1f}%"
            
            return {
                "success": True,
                "team": team_name.title(),
                "project": f"{normalized_name}-infra",
                "period": f"Last {days} days",
                "retrieved_at": datetime.now().isoformat(),
                "mode": f"mock ({scenario_run.scenario_id})",
                "statistics": {
                    "total_deployments": total,
                    "failed_deployments": failed,
                    "rollbacks": 0,
                    "success_rate": success_rate
                },
                "recent_pipelines": team_pipes[:5],
                "infrastructure_changes": []  # Scenarios represent changes directly in pipes for simplicity
            }
        
        if normalized_name not in MOCK_PIPELINE_DATA:
            return {
                "success": False,
                "error": f"Team '{team_name}' not found. Available teams: Release Team, CI Team, CloudOps Team"
            }
        
        data = MOCK_PIPELINE_DATA[normalized_name]
        
        return {
            "success": True,
            "team": data["team"],
            "project": data["project"],
            "period": f"Last {days} days",
            "retrieved_at": datetime.now().isoformat(),
            "statistics": {
                "total_deployments": data["deployment_count_7_days"],
                "failed_deployments": data["failed_deployments_7_days"],
                "rollbacks": data["rollbacks_7_days"],
                "success_rate": f"{((data['deployment_count_7_days'] - data['failed_deployments_7_days']) / max(data['deployment_count_7_days'], 1)) * 100:.1f}%"
            },
            "recent_pipelines": data["recent_pipelines"][:5],
            "infrastructure_changes": data["infrastructure_changes"]
        }
    
    def get_deployment_history(self, team_name: str, days: int = 7) -> dict:
        """
        Get deployment history for a team.
        
        Uses live GitLab API if USE_LIVE_DATA=true, otherwise uses mock data.
        
        Args:
            team_name: Name of the team
            days: Number of days to look back
        
        Returns:
            Dictionary with deployment data
        """
        if _is_mock_mode():
            cache_key = f"mock_{team_name}_{days}"
            cached = self.cache.get("pipeline", team_name=cache_key)
            if cached:
                return cached

            result = self._get_mock_data(team_name, days)
            result["mode"] = self._get_mode_indicator()
            if result.get("success"):
                self.cache.set("pipeline", result, team_name=cache_key)
            return result

        # Check cache
        cache_key = f"{'live' if self._is_live_mode() else 'mock'}_{team_name}_{days}"
        cached = self.cache.get("pipeline", team_name=cache_key)
        if cached:
            return cached
        
        # Get data based on mode
        if self._is_live_mode():
            result = self._get_live_data(team_name, days)
        else:
            result = self._get_mock_data(team_name, days)
        
        # Add mode indicator to result
        result["mode"] = self._get_mode_indicator()
        
        # Cache result
        if result.get("success"):
            self.cache.set("pipeline", result, team_name=cache_key)
        
        return result
    
    def analyze_cost_impact(self, team_name: str, days: int = 7) -> dict:
        """
        Analyze pipeline activity for cost impact using LLM.
        
        Args:
            team_name: Name of the team
            days: Number of days to analyze
        
        Returns:
            Dictionary with analysis results
        """
        deployment_data = self.get_deployment_history(team_name, days)
        
        if not deployment_data.get("success"):
            return deployment_data
        
        # Prepare pipeline summary
        pipeline_summary = []
        for p in deployment_data.get("recent_pipelines", []):
            commit_msg = p.get('commit_message', p.get('commit_title', 'No message'))
            pipeline_summary.append(
                f"- Pipeline #{p['id']} ({str(p['created_at'])[:10]}): {commit_msg} "
                f"[Status: {p['status']}, Duration: {p.get('duration_seconds', p.get('duration', 0))}s]"
            )
        
        # Prepare infrastructure changes
        infra_changes = []
        total_infra_cost = 0
        for change in deployment_data.get("infrastructure_changes", []):
            infra_changes.append(
                f"- {str(change['date'])[:10]}: {change['type']} - {change['description']} "
                f"(Est. monthly cost: ${change['estimated_monthly_cost']})"
            )
            total_infra_cost += change["estimated_monthly_cost"]
        
        if not infra_changes:
            infra_changes = ["No infrastructure changes detected"]
        
        # Run LLM analysis
        chain = self.analysis_prompt | self.llm
        analysis = chain.invoke({
            "team_name": deployment_data["team"],
            "pipeline_summary": "\n".join(pipeline_summary) if pipeline_summary else "No recent pipelines",
            "infra_changes": "\n".join(infra_changes),
            "deployment_count": deployment_data["statistics"]["total_deployments"],
            "failed_count": deployment_data["statistics"]["failed_deployments"],
            "rollback_count": deployment_data["statistics"]["rollbacks"]
        })
        
        return {
            "success": True,
            "team": deployment_data["team"],
            "period": deployment_data["period"],
            "mode": deployment_data.get("mode", self._get_mode_indicator()),
            "statistics": deployment_data["statistics"],
            "estimated_infra_cost_change": f"${total_infra_cost}/month",
            "analysis": analysis.content
        }


# Singleton instance
_pipeline_tool_instance: Optional[PipelineTool] = None


def get_pipeline_tool() -> PipelineTool:
    """Get or create global pipeline tool instance."""
    global _pipeline_tool_instance
    if _pipeline_tool_instance is None:
        _pipeline_tool_instance = PipelineTool()
    return _pipeline_tool_instance


@tool
def pipeline_tool(query: str) -> str:
    """
    Analyze GitLab CI/CD pipeline activity and deployment history.
    
    Use this tool when you need:
    - Deployment history for a team
    - Infrastructure changes from pipelines
    - Cost impact analysis of deployments
    - Correlation between deployments and cost spikes
    
    Args:
        query: Query about pipelines. Include team name if asking about specific team.
               Examples: "release team deployments", "what infrastructure changes happened", "analyze ci team cost impact"
    
    Returns:
        Pipeline activity and cost impact analysis
    """
    tool_instance = get_pipeline_tool()
    query_lower = query.lower()
    
    # Get mode indicator for output
    mode_indicator = tool_instance._get_mode_indicator()
    
    # Determine analysis type
    analyze_cost = "cost" in query_lower or "impact" in query_lower or "analyze" in query_lower or "why" in query_lower
    
    # Find team in query
    for team_key in MOCK_PIPELINE_DATA.keys():
        team_variants = [team_key, team_key.replace("-", " "), team_key.replace("-", "_")]
        if any(v in query_lower for v in team_variants):
            if analyze_cost:
                result = tool_instance.analyze_cost_impact(team_key)
                if not result.get("success"):
                    return result.get("error", "Unknown error occurred")
                
                output = [
                    f"🔧 PIPELINE COST IMPACT ANALYSIS: {result['team']} ({mode_indicator})",
                    f"Period: {result['period']}",
                    "",
                    "📈 DEPLOYMENT STATISTICS:",
                    f"  Total Deployments: {result['statistics']['total_deployments']}",
                    f"  Failed: {result['statistics']['failed_deployments']}",
                    f"  Rollbacks: {result['statistics']['rollbacks']}",
                    f"  Success Rate: {result['statistics']['success_rate']}",
                    "",
                    f"💰 Estimated Infrastructure Cost Change: {result['estimated_infra_cost_change']}",
                    "",
                    "📋 ANALYSIS:",
                    result["analysis"]
                ]
                return "\n".join(output)
            else:
                result = tool_instance.get_deployment_history(team_key)
                if not result.get("success"):
                    return result.get("error", "Unknown error occurred")
                
                output = [
                    f"🚀 DEPLOYMENT HISTORY: {result['team']} ({mode_indicator})",
                    f"Project: {result['project']}",
                    f"Period: {result['period']}",
                    "",
                    "📈 STATISTICS:",
                    f"  Total Deployments: {result['statistics']['total_deployments']}",
                    f"  Success Rate: {result['statistics']['success_rate']}",
                    "",
                    "🔄 RECENT PIPELINES:"
                ]
                
                for p in result.get("recent_pipelines", [])[:3]:
                    commit_msg = p.get('commit_message', p.get('commit_title', 'No message'))
                    output.append(f"  #{p['id']} ({str(p['created_at'])[:10]}): {commit_msg[:50]}...")
                
                if result.get("infrastructure_changes"):
                    output.append("")
                    output.append("🏗️ INFRASTRUCTURE CHANGES:")
                    for change in result["infrastructure_changes"]:
                        output.append(f"  - {change['description']} (${change['estimated_monthly_cost']}/mo)")
                
                return "\n".join(output)
    
    # If no specific team found, provide helpful message with mode indicator
    return f"📡 Pipeline Tool ({mode_indicator})\n\nPlease specify a team name (Release Team, CI Team, or CloudOps Team) to get pipeline data."
