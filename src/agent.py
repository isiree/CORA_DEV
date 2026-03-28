"""
ReAct Agent - Multi-tool orchestrator for cloud cost optimization queries.

Implements the ReAct (Reasoning + Acting) pattern to:
1. Analyze user queries
2. Decide which tools to invoke
3. Chain tool outputs for complex queries
4. Generate comprehensive, sourced answers
"""

import os
from typing import Optional
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.agents import AgentExecutor, create_tool_calling_agent

from .tools import historical_tool, cost_api_tool, pipeline_tool

load_dotenv()


class CloudCostAgent:
    """
    Multi-tool agent for answering cloud cost optimization queries.
    
    Uses three tools:
    1. historical_tool - Search governance documents and policies
    2. cost_api_tool - Get real-time cost data from Azure
    3. pipeline_tool - Analyze CI/CD pipeline activity
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0,
        verbose: bool = True
    ):
        """
        Initialize the agent.
        
        Args:
            model: LLM model name (defaults to env var LLM_MODEL)
            temperature: LLM temperature (0 for deterministic)
            verbose: Whether to print agent reasoning
        """
        self.model_name = model or os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
        self.temperature = temperature
        self.verbose = verbose
        
        self._llm: Optional[ChatGroq] = None
        self._agent_executor: Optional[AgentExecutor] = None
    
    @property
    def llm(self) -> ChatGroq:
        """Lazy-load LLM."""
        if self._llm is None:
            self._llm = ChatGroq(
                model=self.model_name,
                temperature=self.temperature
            )
        return self._llm
    
    @property
    def tools(self) -> list:
        """Get list of available tools."""
        return [historical_tool, cost_api_tool, pipeline_tool]
    
    @property
    def agent_executor(self) -> AgentExecutor:
        """Lazy-load agent executor."""
        if self._agent_executor is None:
            self._agent_executor = self._create_agent()
        return self._agent_executor
    
    def _create_agent(self) -> AgentExecutor:
        """Create the ReAct agent with tools."""
        
        system_prompt = """{scenario_context}You are an expert Cloud Cost Optimization Assistant for ABC Company.

Your role is to help users understand and optimize their cloud spending by:
1. Searching company policies and governance documents
2. Retrieving real-time cost data from Azure
3. Analyzing CI/CD pipeline activity to correlate with costs

IMPORTANT GUIDELINES:
- Always cite your sources (document names, API data, pipeline IDs)
- When asked about budgets, check BOTH the governance documents AND current spending
- When investigating cost spikes, check BOTH the cost API AND pipeline activity
- Provide specific numbers, dates, and recommendations
- If information is incomplete, state what's missing

AVAILABLE TOOLS:
1. historical_tool - Search governance documents for policies, budgets, team info
2. cost_api_tool - Get current spending, budget status, cost breakdown
3. pipeline_tool - Get deployment history, infrastructure changes, cost impact

Think step-by-step:
1. What information does the user need?
2. Which tool(s) should I use?
3. Do I need to chain tools (e.g., get team budget from docs, then check actual spending)?
4. How can I provide the most helpful, actionable answer?

Always end with a clear summary and any relevant recommendations based on ABC Company's policies."""

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        agent = create_tool_calling_agent(self.llm, self.tools, prompt)
        
        return AgentExecutor(
            agent=agent,
            tools=self.tools,
            verbose=self.verbose,
            handle_parsing_errors=True,
            max_iterations=10,
            return_intermediate_steps=True
        )
    
    def query(
        self,
        question: str,
        chat_history: Optional[list] = None,
        scenario_context: Optional[str] = None,
    ) -> dict:
        """
        Process a user query.
        
        Args:
            question: User's question about cloud costs
            chat_history: Optional conversation history
            scenario_context: Optional mock-scenario grounding context
        
        Returns:
            Dictionary with answer and metadata
        """
        scenario_context_block = ""
        if os.getenv("USE_LIVE_DATA", "false").lower() != "true" and scenario_context:
            scenario_context_block = f"{scenario_context.strip()}\n\n"

        input_dict = {
            "input": question,
            "scenario_context": scenario_context_block,
        }
        if chat_history:
            input_dict["chat_history"] = chat_history
        
        result = self.agent_executor.invoke(input_dict)
        
        return {
            "question": question,
            "answer": result["output"],
            "intermediate_steps": result.get("intermediate_steps", []),
            "tools_used": self._extract_tools_used(result.get("intermediate_steps", []))
        }
    
    def _extract_tools_used(self, steps: list) -> list[str]:
        """Extract names of tools used from intermediate steps."""
        tools_used = []
        for action, _ in steps:
            if hasattr(action, "tool"):
                tools_used.append(action.tool)
        return list(set(tools_used))
    
    def get_tool_info(self) -> list[dict]:
        """Get information about available tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in self.tools
        ]


# Singleton instance
_agent_instance: Optional[CloudCostAgent] = None


def get_agent(verbose: bool = True) -> CloudCostAgent:
    """Get or create global agent instance."""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = CloudCostAgent(verbose=verbose)
    return _agent_instance


def ask(question: str, verbose: bool = True) -> str:
    """
    Simple interface to ask a question.
    
    Args:
        question: Your question about cloud costs
        verbose: Whether to show agent reasoning
    
    Returns:
        The agent's answer
    """
    agent = get_agent(verbose=verbose)
    result = agent.query(question)
    return result["answer"]
