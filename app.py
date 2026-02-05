import streamlit as st
from src.agent import CloudCostAgent

st.set_page_config(
    page_title="CORA - Cloud Cost Analyzer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    .stApp {
        background: linear-gradient(180deg, #ffffff 0%, #f0f9f4 100%);
        font-family: 'Inter', sans-serif;
    }

    .st-emotion-cache-1ir3vnm{
    color: #000 !important;
    }
    
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a4d2e 0%, #0d3321 100%);
        border-right: 1px solid #e8f5e9;
    }
    
    [data-testid="stSidebar"] h1 {
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 1.4rem !important;
        text-shadow: 0px 2px 4px rgba(0,0,0,0.3);
        margin-bottom: 20px;
        white-space: nowrap;
    }
    
    [data-testid="stSidebar"] h3 {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        color: #a5d6a7 !important;
    }

    /* Main expander header - all states */
    div[data-testid="stAppViewContainer"] details summary,
    div[data-testid="stAppViewContainer"] details summary:hover,
    div[data-testid="stAppViewContainer"] details summary:focus,
    div[data-testid="stAppViewContainer"] details summary:active,
    div[data-testid="stAppViewContainer"] details[open] summary,
    div[data-testid="stAppViewContainer"] details[open] summary:hover,
    div[data-testid="stAppViewContainer"] details:not([open]) summary,
    div[data-testid="stAppViewContainer"] details:not([open]) summary:hover,
    div[data-testid="stAppViewContainer"] summary[class*="st-emotion-cache"],
    div[data-testid="stAppViewContainer"] summary[class*="st-emotion-cache"]:hover,
    div[data-testid="stAppViewContainer"] .streamlit-expanderHeader,
    div[data-testid="stAppViewContainer"] .streamlit-expanderHeader:hover {
        background: #000000 !important;
        background-color: #000000 !important;
        border: 1px solid #333333 !important;
        color: #ffffff !important;
        opacity: 1 !important;
    }
    
    div[data-testid="stAppViewContainer"] details summary p {
        color: #ffffff !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
    }
    
    div[data-testid="stAppViewContainer"] details summary svg,
    div[data-testid="stAppViewContainer"] details summary span[data-testid="stIconMaterial"] {
        fill: #ffffff !important;
        color: #ffffff !important;
    }

    /* Sidebar expander */
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
    
    .stSelectbox div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #1b5e20 !important;
        font-weight: 500;
        border: 1px solid #e0e0e0;
    }
    
    .stChatMessage {
        background: #ffffff !important;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        padding: 20px;
        margin: 12px 0;
    }
    
    [data-testid="stChatMessage"][data-testid*="user"] {
        background: linear-gradient(135deg, #f1f8f4 0%, #e8f5e9 100%) !important;
        border-left: 4px solid #43a047;
    }
    
    [data-testid="stChatMessage"]:not([data-testid*="user"]) {
        background: #ffffff !important;
        border-left: 4px solid #2e7d32;
    }
    
    .stInfo {
        background-color: rgba(255, 255, 255, 0.1) !important;
        color: #e8f5e9 !important;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }

    .main-title {
        background: linear-gradient(135deg, #2e7d32 0%, #43a047 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
    }
    
    .stChatInputContainer {
        border-radius: 12px;
        border: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.title(" ⚙️ CORA CONTROLS")
st.sidebar.markdown("###  Configuration")
st.sidebar.info("🟢 Live mode active - Connected to Azure & GitLab")
st.sidebar.markdown("###  Team Filter")
team_filter = st.sidebar.selectbox(
    "Select Team", 
    options=["All Teams", "ci-team", "release-team", "cloudops-team"],
    label_visibility="collapsed"
)
st.sidebar.markdown("---")

@st.cache_resource
def init_agent():
    return CloudCostAgent(verbose=False)

agent = init_agent()

# Main UI
st.markdown("""
<div style='text-align: center; padding: 20px 0 40px 0;'>
    <h1 style='font-size: 4rem; margin: 0; letter-spacing: -2px;' class='main-title'>CORA</h1>
    <p style='font-family: "Inter", sans-serif; font-size: 1.2rem; color: #2e7d32; font-weight: 500; margin: 8px 0;'>
        Cloud Optimization & Resource Advisor
    </p>
    <p style='font-family: "Inter", sans-serif; font-size: 1rem; color: #757575;'>
        AI-powered cost investigation and root cause analysis
    </p>
</div>
""", unsafe_allow_html=True)

with st.expander("🛠️ AVAILABLE INVESTIGATION TOOLS", expanded=True):
    tools_info = agent.get_tool_info()
    cols = st.columns(3)
    for i, tool in enumerate(tools_info):
        with cols[i % 3]:
            st.markdown(f"""
            <div style='background: white; border: 1px solid #e0e0e0; border-radius: 10px;
                padding: 15px; margin: 5px 0; box-shadow: 0 2px 5px rgba(0,0,0,0.05);'>
                <div style='color: #2e7d32; font-size: 1.2em; margin-bottom: 5px;'>🔎 <strong>{tool['name']}</strong></div>
                <div style='color: #616161; font-size: 0.9em; line-height: 1.4;'>{tool['description']}</div>
            </div>
            """, unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"], avatar="👤" if message["role"] == "user" else "🤖"):
        st.markdown(message["content"])

if prompt := st.chat_input("🔍 Start your investigation... (e.g., 'Why did CI team costs increase last week?')"):
    full_query = f"For {team_filter}: {prompt}" if team_filter != "All Teams" else prompt
    
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
                            st.markdown(f"*Query:* ⁠ {tool_input} ⁠")
                            obs_preview = str(observation)[:800]
                            if len(str(observation)) > 800:
                                obs_preview += "... [truncated]"
                            st.markdown(f"*Result:* {obs_preview}")
                
                tools_used = result.get('tools_used', [])
                if tools_used:
                    st.markdown(f"*🔧 Tools Used:* {', '.join(tools_used)}")
                
                st.markdown("---")
                st.markdown("### ✅ Investigation Complete")
                st.markdown(result['answer'])
                
                full_response = f"*Tools:* {', '.join(tools_used)}\n\n{result['answer']}"
                st.session_state.messages.append({"role": "assistant", "content": full_response})
            except Exception as e:
                st.error(f"❌ Investigation failed: {str(e)}")

with st.sidebar.expander("💡 Example Queries"):
    st.markdown("""
    <div style='color: white;'>
    <strong>Budget:</strong><br>- Release Team's monthly budget?<br>- Is anyone over budget?<br><br>
    <strong>Trends:</strong><br>- Why did costs spike?<br>- Breakdown by team<br><br>
    <strong>Infrastructure:</strong><br>- List CI team resources<br>- Recent changes?
    </div>
    """, unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown("""
<div style='font-size: 0.8rem; color: #a5d6a7; text-align: center;'>
    <strong>CORA v1.0</strong><br>Azure • GitLab • Groq
</div>
""", unsafe_allow_html=True)