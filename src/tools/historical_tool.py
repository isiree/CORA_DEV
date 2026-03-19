"""
Historical Tool - RAG-based document search for policies and governance.

Searches through ABC Company's indexed documents (PDF, Markdown, text, DOCX)
including:
- Team subscriptions and budget allocations
- Cost governance policies
- FinOps frameworks
- Multicloud strategies
- AI automation best practices
"""

from typing import Optional
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
import os
from dotenv import load_dotenv

from ..utils.rag_retriever import get_retriever

load_dotenv()


class HistoricalTool:
    """
    Tool for searching historical documents and policies.
    Uses RAG with ChromaDB for semantic search.
    """
    
    def __init__(self, llm: Optional[ChatGroq] = None):
        self.retriever = get_retriever()
        self.llm = llm or ChatGroq(
            model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile"),
            temperature=0
        )
        
        self.summarization_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a helpful assistant that summarizes document search results.
Given the search results below, provide a concise summary that directly answers the user's query.
Include specific details like numbers, team names, budget amounts, and policy details.
Always cite the source document for each piece of information.

Format your response as:
- Key finding 1 (Source: document_name.pdf)
- Key finding 2 (Source: document_name.pdf)
..."""),
            ("human", """Query: {query}

Search Results:
{results}

Provide a concise, factual summary:""")
        ])
    
    def search(
        self,
        query: str,
        top_k: int = 3,
        summarize: bool = True
    ) -> dict:
        """
        Search documents and optionally summarize results.
        
        Args:
            query: Search query about policies, budgets, teams, etc.
            top_k: Number of documents to retrieve
            summarize: Whether to use LLM to summarize results
        
        Returns:
            Dictionary with raw results and optional summary
        """
        # Retrieve relevant documents
        results = self.retriever.retrieve(query, top_k=top_k)
        
        if not results:
            return {
                "success": False,
                "message": "No relevant documents found for query.",
                "query": query,
                "results": [],
                "summary": None
            }
        
        # Format results for output
        formatted_results = []
        for i, r in enumerate(results, 1):
            formatted_results.append({
                "rank": i,
                "content": r["content"],
                "source": r["metadata"].get("source", "Unknown"),
                "page": r["metadata"].get("page", "N/A"),
                "similarity": r["similarity"]
            })
        
        response = {
            "success": True,
            "query": query,
            "results": formatted_results,
            "summary": None
        }
        
        # Generate summary if requested
        if summarize and self.llm:
            results_text = "\n\n".join([
                f"[Result {r['rank']}] (Source: {r['source']}, Similarity: {r['similarity']})\n{r['content']}"
                for r in formatted_results
            ])
            
            chain = self.summarization_prompt | self.llm
            summary_response = chain.invoke({
                "query": query,
                "results": results_text
            })
            sources = []
            seen = set()
            for r in formatted_results:
                src = r.get("source")
                if src and src not in seen:
                    seen.add(src)
                    sources.append(src)
            sources_block = "\n".join([f"- {s}" for s in sources]) if sources else "- Unknown"
            response["summary"] = f\"{summary_response.content.strip()}\\n\\nSources:\\n{sources_block}\"
        
        return response


# Create singleton instance
_historical_tool_instance: Optional[HistoricalTool] = None


def get_historical_tool() -> HistoricalTool:
    """Get or create global historical tool instance."""
    global _historical_tool_instance
    if _historical_tool_instance is None:
        _historical_tool_instance = HistoricalTool()
    return _historical_tool_instance


@tool
def historical_tool(query: str) -> str:
    """
    Search ABC Company's historical documents for policies, budgets, team information, and governance.
    
    Use this tool when you need information about:
    - Team budget allocations and spending limits
    - Cost governance policies and thresholds
    - Resource tagging requirements
    - FinOps maturity and practices
    - Multicloud strategy
    - AI/automation initiatives
    
    Args:
        query: Natural language query about company policies or historical data
    
    Returns:
        Summary of relevant information with source citations
    """
    tool_instance = get_historical_tool()
    result = tool_instance.search(query, top_k=3, summarize=True)
    
    if not result["success"]:
        return f"No relevant documents found for: {query}"
    
    # Return the summary for the agent
    if result["summary"]:
        return result["summary"]
    
    # Fallback to raw results if no summary
    output_parts = [f"Found {len(result['results'])} relevant documents:"]
    for r in result["results"]:
        output_parts.append(f"\n[{r['source']}] (Similarity: {r['similarity']})")
        output_parts.append(r["content"][:500] + "..." if len(r["content"]) > 500 else r["content"])
    
    return "\n".join(output_parts)
