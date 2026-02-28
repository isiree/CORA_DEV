# IMRAG - Intelligent Multi-tool RAG for Cloud Cost Optimization

A production-ready Multi-Tool Retrieval-Augmented Generation (RAG) Agent system designed to intelligently answer cloud cost optimization questions by integrating three specialized data sources through a coordinated ReAct (Reasoning + Acting) orchestration pattern.

## 🎯 Overview

This system helps ABC Company's teams understand and optimize their cloud spending by:
- **Searching historical governance documents** (policies, budgets, team allocations)
- **Retrieving real-time cost data** from Azure Cost Management API
- **Analyzing CI/CD pipeline activity** to correlate deployments with cost changes

## 🏗️ Architecture

```
User Query
    ↓
[ReAct Agent] (LLM: Groq/Llama-3.3-70b)
    ↓
Decides which tools to use:
    ├── historical_tool → ChromaDB (RAG) → Policy/Budget Info
    ├── cost_api_tool → Azure API → Current Spending Data
    └── pipeline_tool → GitLab API → Deployment Activity
    ↓
[Agent synthesizes responses]
    ↓
Comprehensive Answer with Sources
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your API keys
# Required: GROQ_API_KEY
```

### 3. Generate Demo PDFs (Optional)

```bash
uv run python scripts/generate_pdfs.py
```

### 4. Run CLI Demo

```bash
uv run python main.py
```

### 5. Run React Web UI

```bash
# Uses app.py as the API/static server
.venv/bin/python app.py
```

Then open [http://localhost:8501](http://localhost:8501).

## 📁 Project Structure

```
imrag/
├── src/
│   ├── agent.py              # ReAct agent orchestrator
│   ├── tools/
│   │   ├── historical_tool.py  # RAG document search
│   │   ├── cost_api_tool.py    # Azure Cost Management
│   │   └── pipeline_tool.py    # GitLab CI/CD analysis
│   └── utils/
│       ├── rag_retriever.py    # ChromaDB wrapper
│       └── cache_manager.py    # Caching layer
├── static/
│   ├── app.js                # React frontend (no build step)
│   └── styles.css            # UI styling
├── templates/
│   └── index.html            # UI shell
├── data/
│   ├── pdf_files/            # Source documents
│   ├── vector_db/            # ChromaDB persistence
│   └── cache/                # Tool output cache
├── scripts/
│   └── generate_pdfs.py      # Demo data generator
├── main.py                   # CLI demo entry point
└── app.py                    # React UI + API server
```

## 💬 Example Queries

```
• "What is the Release Team's monthly budget?"
• "Is the Release Team over budget? What's the status?"
• "Why did the Release Team's costs increase last week?"
• "What are the cost escalation thresholds?"
• "Show me all teams' spending summary"
```

## 🔧 Tools

### 1. Historical Tool
Searches ABC Company's governance documents using semantic search (ChromaDB + SentenceTransformers).

**Use for:** Policies, budgets, team info, governance rules

### 2. Cost API Tool  
Retrieves real-time spending data from Azure Cost Management API.

**Use for:** Current spend, budget status, cost breakdown, anomalies

### 3. Pipeline Tool
Analyzes GitLab CI/CD pipeline activity and infrastructure changes.

**Use for:** Deployment history, infra changes, cost impact correlation

## 📊 Demo Data

The demo uses mock data for Azure and GitLab APIs that simulates:
- 3 teams (Release, CI, CloudOps)
- Budget allocations and current spending
- Deployment activity and infrastructure changes
- Cost anomalies and alerts

## 🔜 Future Enhancements

- [ ] Real Azure Cost Management API integration
- [ ] Real GitLab API integration  
- [ ] Multi-tenant authentication
- [ ] PostgreSQL persistence
- [ ] Web dashboard UI
- [ ] Compliance reporting

## 📄 License

MIT License
