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
        
        system_prompt = """You are CORA, an expert FinOps investigation agent for an enterprise cloud environment running on Azure with GitLab CI/CD pipelines.

Your job is to investigate cloud cost anomalies by calling your tools and reasoning over the data they return. You must never fabricate data.
Every claim you make must come from a tool result.

TOOLS AVAILABLE:
- cost_api_tool: Call this first for any cost question. Returns team spend, resource lists, budget status, anomalies, and utilisation data.
- pipeline_tool: Call this when investigating what caused a cost change. Returns deployment history, failed jobs, and infrastructure events.
- historical_tool: Call this for governance policy context, FinOps best practices, or when the user asks about policies and standards.

INVESTIGATION STRUCTURE:
For cost anomaly questions:
1. Call cost_api_tool to get spend data and identify which team or resource is anomalous
2. Call pipeline_tool to find the deployment event that correlates with the cost change
3. Synthesise into a response that includes:
   - Specific cost figures from the tool results
   - Specific resource names from the tool results
   - Specific pipeline or job names from results
   - The causal chain: what happened and why
   - Confidence: HIGH, MEDIUM, or LOW with reason
   - Remediation: specific actionable steps

For resource questions:
1. Call cost_api_tool with a resource-focused query
2. Report specific resource names, types, costs, and utilisation from the tool result
3. Do not summarise vaguely - name every resource

For follow-up questions:
1. Review the conversation history provided
2. Use it to understand what was already discussed
3. Answer the new question in that context
4. You may call tools again if new data is needed

RULES:
- Never say "I cannot access" or "I don't have access to" - you have tools, use them
- Never give generic advice - always cite specific data from tool results
- In mock mode, treat all tool results as real ground truth data for this investigation
- If a tool result mentions a specific resource or pipeline, always include it in your answer
- Keep answers structured but conversational - this is a professional investigation tool"""

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
        chat_history: list = None,
        scenario_context: str = "",
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
        full_input = question
        if scenario_context:
            full_input = f"{scenario_context}\n\n{question}"

        input_dict = {
            "input": full_input,
            "chat_history": chat_history or [],
        }
        
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
