"""
Flask/FastAPI web application - DORMANT for demo.
Will be implemented for production web dashboard.
"""

# This file is intentionally minimal for the demo.
# The demo runs via main.py command line interface.
# 
# Production will add:
# - Flask/FastAPI REST API
# - WebSocket for streaming responses
# - Authentication middleware
# - Rate limiting

import streamlit as st
from src.agent import CloudCostAgent
import os

# Page config
st.set_page_config(
    page_title="CORA - Cloud Cost Analyzer",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar for configuration
st.sidebar.title("🔧 Configuration")
st.sidebar.markdown("**API Mode Status:**")
st.sidebar.info("Tools auto-detect mock/live mode from .env settings")

team_filter = st.sidebar.selectbox(
    "Team Filter", 
    options=["All", "ci-team", "release-team", "cloudops-team"]
)

# Initialize agent (singleton pattern from your code)
@st.cache_resource
def init_agent():
    return CloudCostAgent(verbose=False)  # Set verbose=False for cleaner UI

agent = init_agent()

# Main UI
st.title("☁️ IMRAG - Cloud Cost Optimization Assistant")
st.markdown("**AI-Powered Root Cause Analysis for ABC Company**")

# Show available tools
with st.expander("🔧 Available Tools"):
    tools_info = agent.get_tool_info()
    for tool in tools_info:
        st.markdown(f"**{tool['name']}**: {tool['description']}")

# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask about costs, deployments, or infrastructure..."):
    # Enhance query with team filter if specified
    if team_filter != "All":
        full_query = f"For {team_filter}: {prompt}"
    else:
        full_query = prompt
    
    # Add user message
    st.session_state.messages.append({"role": "user", "content": full_query})
    with st.chat_message("user"):
        st.markdown(full_query)

    # Run agent
    with st.chat_message("assistant"):
        with st.spinner("🤖 Analyzing your query..."):
            try:
                # Call agent's query method (from your agent.py)
                result = agent.query(full_query)
                
                # Show intermediate steps (tool calls)
                steps = result.get('intermediate_steps', [])
                if steps:
                    st.markdown("**🔍 Agent Reasoning Steps:**")
                    for i, (action, observation) in enumerate(steps[:5], 1):  # Limit to 5 steps
                        tool_name = action.tool if hasattr(action, 'tool') else 'Unknown'
                        tool_input = action.tool_input if hasattr(action, 'tool_input') else {}
                        
                        with st.expander(f"Step {i}: {tool_name}", expanded=(i==1)):
                            st.markdown(f"**Query:** `{tool_input}`")
                            # Truncate long observations
                            obs_preview = str(observation)[:800]
                            if len(str(observation)) > 800:
                                obs_preview += "... [truncated]"
                            st.markdown(f"**Result:** {obs_preview}")
                
                # Tools used summary
                tools_used = result.get('tools_used', [])
                if tools_used:
                    st.markdown(f"**🛠️ Tools Used:** {', '.join(tools_used)}")
                
                # Final answer
                st.markdown("---")
                st.markdown("**✅ Final Analysis:**")
                st.markdown(result['answer'])
                
                # Save to history
                full_response = f"**Tools:** {', '.join(tools_used)}\n\n{result['answer']}"
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"❌ Agent Error: {str(e)}")
                st.info("Check that your .env file is configured and tools are accessible.")

# Demo queries sidebar
with st.sidebar.expander("💡 Example Queries"):
    st.markdown("""
    - "What is the Release Team's monthly budget?"
    - "Is the Release Team over budget?"
    - "Why did costs increase?"
    - "Show CI team infrastructure"
    - "List all resources for cloudops team"
    - "What are ABC Company's cost policies?"
    """)
    
# Footer
st.markdown("---")
st.markdown("*Powered by Groq LLM, Azure Cost Management API & GitLab CI/CD*")
st.caption(f"Agent: {agent.model_name} | Tools: historical_tool, cost_api_tool, pipeline_tool")
