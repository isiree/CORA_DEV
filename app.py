import streamlit as st
from src.agent import CloudCostAgent
import os
import sys

st.set_page_config(
    page_title="CORA - Cloud Cost Analyzer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS - Complete with all visibility fixes
st.markdown("""
<style>
    /* Import modern font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Main background */
    .stApp {
        background: linear-gradient(180deg, #ffffff 0%, #f0f9f4 100%);
        font-family: 'Inter', sans-serif;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a4d2e 0%, #0d3321 100%);
        border-right: 1px solid #e8f5e9;
    }
    
    /* Sidebar Title */
    [data-testid="stSidebar"] h1 {
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 1.4rem !important;
        letter-spacing: 0px;
        text-shadow: 0px 2px 4px rgba(0,0,0,0.3);
        margin-bottom: 20px;
        white-space: nowrap;
    }
    
    /* ===================================================================
       GLOBAL FIX: Force ALL text in main area to be visible
       =================================================================== */
    
    /* Force all text elements in main content area to be dark */
    div[data-testid="stAppViewContainer"] p,
    div[data-testid="stAppViewContainer"] div,
    div[data-testid="stAppViewContainer"] span,
    div[data-testid="stAppViewContainer"] li,
    div[data-testid="stAppViewContainer"] strong,
    div[data-testid="stAppViewContainer"] em,
    div[data-testid="stAppViewContainer"] label {
        color: #1a1a1a !important;
    }
    
    /* All headers in main area should be dark green */
    div[data-testid="stAppViewContainer"] h1,
    div[data-testid="stAppViewContainer"] h2,
    div[data-testid="stAppViewContainer"] h3,
    div[data-testid="stAppViewContainer"] h4,
    div[data-testid="stAppViewContainer"] h5,
    div[data-testid="stAppViewContainer"] h6 {
        color: #2e7d32 !important;
    }
    
    /* ===================================================================*/
    
    /* Main Area Expander Headers */
    div[data-testid="stAppViewContainer"] .streamlit-expanderHeader {
        background-color: #000000 !important;
        border: 1px solid #333333 !important;
        color: #ffffff !important;
        opacity: 1 !important;
    }
    
    div[data-testid="stAppViewContainer"] .streamlit-expanderHeader p {
        color: #ffffff !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        visibility: visible !important;
    }
    
    div[data-testid="stAppViewContainer"] .streamlit-expanderHeader svg {
        fill: #ffffff !important;
        color: #ffffff !important;
        visibility: visible !important;
    }
    
    div[data-testid="stAppViewContainer"] .streamlit-expanderHeader:hover {
        background-color: #1a1a1a !important;
        color: #ffffff !important;
    }
    
    /* Content INSIDE expanders should have white background and dark text */
    div[data-testid="stAppViewContainer"] .streamlit-expanderContent {
        background-color: #ffffff !important;
    }
    
    div[data-testid="stAppViewContainer"] .streamlit-expanderContent p,
    div[data-testid="stAppViewContainer"] .streamlit-expanderContent div,
    div[data-testid="stAppViewContainer"] .streamlit-expanderContent span {
        color: #1a1a1a !important;
    }

    /* Sidebar Expander */
    [data-testid="stSidebar"] .streamlit-expanderHeader {
        background-color: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        color: #ffffff !important;
    }
    
    [data-testid="stSidebar"] .streamlit-expanderHeader p,
    [data-testid="stSidebar"] .streamlit-expanderHeader svg {
        color: #ffffff !important;
        fill: #ffffff !important;
    }

    /* Configuration headers */
    [data-testid="stSidebar"] h3 {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        color: #a5d6a7 !important;
    }
    
    /* Team Filter Dropdown */
    .stSelectbox div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #1b5e20 !important;
        font-weight: 500;
        border: 1px solid #e0e0e0;
    }
    
    /* Chat Messages */
    .stChatMessage {
        background: #ffffff !important;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px;
        margin: 12px 0;
    }
    
    /* Force all text inside chat messages to be dark */
    .stChatMessage p,
    .stChatMessage div,
    .stChatMessage span,
    .stChatMessage li,
    .stChatMessage strong,
    .stChatMessage em,
    .stChatMessage code {
        color: #1a1a1a !important;
    }
    
    /* User message */
    [data-testid="stChatMessage"][data-testid*="user"] {
        background: linear-gradient(135deg, #f1f8f4 0%, #e8f5e9 100%) !important;
        border-left: 4px solid #43a047;
    }
    
    /* Assistant message */
    [data-testid="stChatMessage"]:not([data-testid*="user"]) {
        background: #ffffff !important;
        border-left: 4px solid #2e7d32;
    }
    
    /* Headers inside chat */
    .stChatMessage h1,
    .stChatMessage h2,
    .stChatMessage h3,
    .stChatMessage h4 {
        color: #2e7d32 !important;
    }
    
    /* Code blocks */
    .stChatMessage code,
    div[data-testid="stAppViewContainer"] code {
        background-color: #f5f5f5 !important;
        color: #c7254e !important;
        padding: 2px 4px;
        border-radius: 3px;
    }
    
    /* Pre-formatted text blocks */
    .stChatMessage pre,
    div[data-testid="stAppViewContainer"] pre {
        background-color: #f5f5f5 !important;
        color: #1a1a1a !important;
        padding: 10px;
        border-radius: 5px;
        border: 1px solid #e0e0e0;
    }
    
    /* Info boxes */
    .stInfo {
        background-color: rgba(255, 255, 255, 0.1) !important;
        color: #e8f5e9 !important;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }

    /* Main Title */
    .main-title {
        background: linear-gradient(135deg, #2e7d32 0%, #43a047 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    
    /* Input field */
    .stChatInputContainer {
        border-radius: 12px;
        border: 1px solid #e0e0e0;
    }
    
    /* Markdown content */
    .stMarkdown {
        color: #1a1a1a !important;
    }
</style>
""", unsafe_allow_html=True)


# ============================================
# MODE TOGGLE FUNCTIONALITY
# ============================================

def reset_providers():
    """Reset all provider singletons to force reinitialization"""
    try:
        # Import the actual modules (not __init__)
        import src.providers
        import src.tools.cost_api_tool
        import src.tools.pipeline_tool
        
        # Reset provider singleton
        if hasattr(src.providers, '_cost_provider_instance'):
            src.providers._cost_provider_instance = None
        
        # Reset tool singletons
        if hasattr(src.tools.cost_api_tool, '_cost_tool_instance'):
            src.tools.cost_api_tool._cost_tool_instance = None
        
        if hasattr(src.tools.pipeline_tool, '_pipeline_tool_instance'):
            src.tools.pipeline_tool._pipeline_tool_instance = None
            
    except Exception as e:
        # If reset fails, we'll just let st.cache_resource.clear() handle it
        pass


def update_mode(new_mode):
    """Update the data mode and reset providers"""
    # Update environment variable
    os.environ["USE_LIVE_DATA"] = "true" if new_mode == "Live" else "false"
    
    # Reset all cached providers
    reset_providers()
    
    # Clear agent cache to force reinit
    st.cache_resource.clear()


# Initialize session state for mode
if "data_mode" not in st.session_state:
    # Read current mode from environment
    current_mode = "Live" if os.getenv("USE_LIVE_DATA", "false").lower() == "true" else "Mock"
    st.session_state.data_mode = current_mode


# Sidebar
st.sidebar.title(" ⚙️ CORA CONTROLS")
st.sidebar.markdown("### Configuration")


# ============================================
# MODE TOGGLE SWITCH
# ============================================
st.sidebar.markdown("### 🔄 Data Mode")

mode_options = ["Mock", "Live"]
current_index = mode_options.index(st.session_state.data_mode)

selected_mode = st.sidebar.radio(
    "Select Data Source",
    options=mode_options,
    index=current_index,
    horizontal=True,
    label_visibility="collapsed",
    help="Mock: Use demo data | Live: Connect to Azure & GitLab APIs"
)

# Detect mode change and update
if selected_mode != st.session_state.data_mode:
    st.session_state.data_mode = selected_mode
    update_mode(selected_mode)
    st.rerun()


# Mode indicator
if st.session_state.data_mode == "Live":
    st.sidebar.success("🟢 Live mode - Connected to Azure & GitLab")
else:
    st.sidebar.warning("🟡 Mock mode - Using demo data")


st.sidebar.markdown("---")


# Team filter
st.sidebar.markdown("### Team Filter")
team_filter = st.sidebar.selectbox(
    "Select Team", 
    options=["All Teams", "ci-team", "release-team", "cloudops-team"],
    label_visibility="collapsed"
)


st.sidebar.markdown("---")


# Initialize agent (will use current mode)
@st.cache_resource
def init_agent():
    return CloudCostAgent(verbose=False)


agent = init_agent()


# Main UI
st.markdown("""
<div style='text-align: center; padding: 20px 0 40px 0;'>
    <h1 style='font-size: 4rem; margin: 0; letter-spacing: -2px;' class='main-title'>
        CORA
    </h1>
    <p style='font-family: "Inter", sans-serif; font-size: 1.2rem; color: #2e7d32; font-weight: 500; margin: 8px 0;'>
        Cloud Optimization & Resource Advisor
    </p>
    <p style='font-family: "Inter", sans-serif; font-size: 1rem; color: #757575;'>
        AI-powered cost investigation and root cause analysis
    </p>
</div>
""", unsafe_allow_html=True)


# Tools expander
with st.expander("🛠️ AVAILABLE INVESTIGATION TOOLS", expanded=True):
    tools_info = agent.get_tool_info()
    cols = st.columns(3)
    for i, tool in enumerate(tools_info):
        with cols[i % 3]:
            st.markdown(f"""
            <div style='
                background: white; 
                border: 1px solid #e0e0e0; 
                border-radius: 10px;
                padding: 15px; 
                margin: 5px 0;
                box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            '>
                <div style='color: #2e7d32; font-size: 1.2em; margin-bottom: 5px;'>🔎 <strong>{tool['name']}</strong></div>
                <div style='color: #616161; font-size: 0.9em; line-height: 1.4;'>{tool['description']}</div>
            </div>
            """, unsafe_allow_html=True)


# Chat history
if "messages" not in st.session_state:
    st.session_state.messages = []


# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else "🤖"):
        st.markdown(message["content"])


# Chat input
if prompt := st.chat_input("🔍 Start your investigation... (e.g., 'Why did CI team costs increase last week?')"):
    if team_filter != "All Teams":
        full_query = f"For {team_filter}: {prompt}"
    else:
        full_query = prompt
    
    st.session_state.messages.append({"role": "user", "content": full_query})
    with st.chat_message("user", avatar="👤"):
        st.markdown(full_query)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("🔍 Analyzing data..."):
            try:
                result = agent.query(full_query)
                steps = result.get('intermediate_steps', [])
                if steps:
                    st.markdown("### 📋 Investigation Steps")
                    for i, (action, observation) in enumerate(steps[:5], 1):
                        tool_name = action.tool if hasattr(action, 'tool') else 'Unknown'
                        tool_input = action.tool_input if hasattr(action, 'tool_input') else {}
                        
                        with st.expander(f"Step {i}: {tool_name}", expanded=(i==1)):
                            st.markdown(f"**Query:** `{tool_input}`")
                            obs_preview = str(observation)[:800]
                            if len(str(observation)) > 800:
                                obs_preview += "... [truncated]"
                            st.markdown(f"**Result:** {obs_preview}")
                
                tools_used = result.get('tools_used', [])
                if tools_used:
                    st.markdown(f"**🔧 Tools Used:** {', '.join(tools_used)}")
                
                st.markdown("---")
                st.markdown("### ✅ Investigation Complete")
                st.markdown(result['answer'])
                
                full_response = f"**Tools:** {', '.join(tools_used)}\n\n{result['answer']}"
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
            except Exception as e:
                st.error(f"❌ Investigation failed: {str(e)}")


# Example queries in sidebar
with st.sidebar.expander("💡 Example Queries"):
    st.markdown("""
    <div style='color: white;'>
    <strong> Budget:</strong><br>
    - Release Team's monthly budget?<br>
    - Is anyone over budget?<br><br>
    <strong> Trends:</strong><br>
    - Why did costs spike?<br>
    - Breakdown by team<br><br>
    <strong> Infrastructure:</strong><br>
    - List CI team resources<br>
    - Recent changes?
    </div>
    """, unsafe_allow_html=True)


st.sidebar.markdown("---")
st.sidebar.markdown(f"""
<div style='font-size: 0.8rem; color: #a5d6a7; text-align: center;'>
    <strong>CORA v1.0</strong><br>
    Azure • GitLab • Groq<br>
    <em>{st.session_state.data_mode} Mode</em>
</div>
""", unsafe_allow_html=True)

