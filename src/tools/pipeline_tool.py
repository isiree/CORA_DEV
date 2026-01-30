"""
Pipeline Tool - GitLab CI/CD pipeline analysis.

Analyzes deployment history, infrastructure changes, and pipeline activity
to correlate with cost changes. Uses LLM to extract insights from logs.

For demo purposes, uses mock data simulating GitLab CI/CD responses.
"""

import os
from datetime import datetime, timedelta
from typing import Optional
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

from ..utils.cache_manager import get_cache

load_dotenv()


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
    
    def _normalize_team_name(self, team_name: str) -> str:
        """Normalize team name for lookup."""
        return team_name.lower().replace(" ", "-").replace("_", "-")
    
    def get_deployment_history(self, team_name: str, days: int = 7) -> dict:
        """
        Get deployment history for a team.
        
        Args:
            team_name: Name of the team
            days: Number of days to look back
        
        Returns:
            Dictionary with deployment data
        """
        # Check cache
        cached = self.cache.get("pipeline", team_name=team_name, days=days)
        if cached:
            return cached
        
        normalized_name = self._normalize_team_name(team_name)
        
        if normalized_name not in MOCK_PIPELINE_DATA:
            return {
                "success": False,
                "error": f"Team '{team_name}' not found. Available teams: Release Team, CI Team, CloudOps Team"
            }
        
        data = MOCK_PIPELINE_DATA[normalized_name]
        
        result = {
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
        
        # Cache result
        self.cache.set("pipeline", result, team_name=team_name, days=days)
        
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
        
        if not deployment_data["success"]:
            return deployment_data
        
        # Prepare pipeline summary
        pipeline_summary = []
        for p in deployment_data["recent_pipelines"]:
            pipeline_summary.append(
                f"- Pipeline #{p['id']} ({p['created_at'][:10]}): {p['commit_message']} "
                f"[Status: {p['status']}, Duration: {p['duration_seconds']}s]"
            )
        
        # Prepare infrastructure changes
        infra_changes = []
        total_infra_cost = 0
        for change in deployment_data["infrastructure_changes"]:
            infra_changes.append(
                f"- {change['date'][:10]}: {change['type']} - {change['description']} "
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
    
    # Determine analysis type
    analyze_cost = "cost" in query_lower or "impact" in query_lower or "analyze" in query_lower or "why" in query_lower
    
    # Find team in query
    for team_key in MOCK_PIPELINE_DATA.keys():
        team_variants = [team_key, team_key.replace("-", " "), team_key.replace("-", "_")]
        if any(v in query_lower for v in team_variants):
            if analyze_cost:
                result = tool_instance.analyze_cost_impact(team_key)
                if not result["success"]:
                    return result["error"]
                
                output = [
                    f"🔧 PIPELINE COST IMPACT ANALYSIS: {result['team']}",
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
                if not result["success"]:
                    return result["error"]
                
                output = [
                    f"🚀 DEPLOYMENT HISTORY: {result['team']}",
                    f"Project: {result['project']}",
                    f"Period: {result['period']}",
                    "",
                    "📈 STATISTICS:",
                    f"  Total Deployments: {result['statistics']['total_deployments']}",
                    f"  Success Rate: {result['statistics']['success_rate']}",
                    "",
                    "🔄 RECENT PIPELINES:"
                ]
                
                for p in result["recent_pipelines"][:3]:
                    output.append(f"  #{p['id']} ({p['created_at'][:10]}): {p['commit_message'][:50]}...")
                
                if result["infrastructure_changes"]:
                    output.append("")
                    output.append("🏗️ INFRASTRUCTURE CHANGES:")
                    for change in result["infrastructure_changes"]:
                        output.append(f"  - {change['description']} (${change['estimated_monthly_cost']}/mo)")
                
                return "\n".join(output)
    
    return "Please specify a team name (Release Team, CI Team, or CloudOps Team) to get pipeline data."
