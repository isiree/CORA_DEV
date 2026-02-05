"""
IMRAG - Intelligent Multi-tool RAG for Cloud Cost Optimization

Main entry point for running the demo.
"""

import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()


def check_environment():
    """Check that required environment variables are set."""
    required_vars = ["GROQ_API_KEY"]
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        print("❌ Missing required environment variables:")
        for var in missing:
            print(f"   - {var}")
        print("\nPlease copy .env.example to .env and fill in your API keys.")
        print("\n📝 To get a free GROQ API key:")
        print("   1. Go to https://console.groq.com")
        print("   2. Sign up (free)")
        print("   3. Create an API key")
        print("   4. Add it to your .env file as GROQ_API_KEY=your_key_here")
        return False
    
    print("✅ Environment configured correctly")
    return True


def check_vector_db():
    """Check if vector database exists."""
    db_path = Path(os.getenv("CHROMA_PERSIST_DIR", "data/vector_db"))
    if not db_path.exists() or not any(db_path.iterdir()):
        print("⚠️  Vector database not found at:", db_path)
        print("   Run the PDF loader notebook first to create the database.")
        return False
    
    print("✅ Vector database found")
    return True


def check_api_mode():
    """Check if using real APIs or mock data."""
    from src.providers import is_live_mode, is_azure_live_mode, is_gitlab_live_mode
    
    live_mode = is_live_mode()
    azure_live = is_azure_live_mode()
    gitlab_live = is_gitlab_live_mode()
    
    print("\n📡 API Mode Status:")
    
    # Azure status
    if azure_live:
        print("   ✅ Azure Cost Management: LIVE (real data)")
    else:
        print("   🎭 Azure Cost Management: MOCK DATA (demo mode)")
        print("      ℹ️  For Azure CLI auth, ensure you've run 'az login'")
    
    # GitLab status - now correctly checks USE_LIVE_DATA
    if gitlab_live:
        print("   ✅ GitLab CI/CD: LIVE (real data)")
    else:
        print("   🎭 GitLab CI/CD: MOCK DATA (demo mode)")
    
    # Informational messages
    if not live_mode:
        print("\n   ℹ️  USE_LIVE_DATA=false in .env (demo mode enabled)")
        print("   ℹ️  Mock data simulates ABC Company's cloud spending.")
        print("   ℹ️  Set USE_LIVE_DATA=true for production use.")
    elif not azure_live or not gitlab_live:
        print("\n   ℹ️  Live mode enabled but some credentials missing:")
        if not azure_live:
            print("      - Azure: Missing AZURE_TENANT_ID, AZURE_CLIENT_ID, or AZURE_CLIENT_SECRET")
        if not gitlab_live:
            print("      - GitLab: Missing GITLAB_TOKEN or GITLAB_PROJECT_ID")
        print("   ℹ️  Add missing credentials in .env for full live mode.")


def run_demo():
    """Run interactive demo."""
    from src.agent import get_agent
    
    print("\n" + "=" * 60)
    print("🤖 ABC Company Cloud Cost Optimization Assistant")
    print("=" * 60)
    print("\nI can help you with:")
    print("  • Team budget and spending information")
    print("  • Cost governance policies")
    print("  • Cost spike root cause analysis")
    print("  • Deployment and infrastructure changes")
    print("\nType 'quit' to exit, 'tools' to see available tools")
    print("-" * 60)
    
    agent = get_agent(verbose=True)
    
    # Demo questions
    demo_questions = [
        "What is the Release Team's monthly budget?",
        "Is the Release Team over budget? What's the status?",
        "Why did the Release Team's costs increase?",
        "What are ABC Company's cost governance policies?",
        "Show me all teams' spending summary"
    ]
    
    print("\n📋 DEMO QUESTIONS (copy & paste):")
    for i, q in enumerate(demo_questions, 1):
        print(f"   {i}. {q}")
    print()
    
    while True:
        try:
            question = input("\n💬 Your question: ").strip()
            
            if not question:
                continue
            
            if question.lower() == "quit":
                print("\nGoodbye! 👋")
                break
            
            if question.lower() == "tools":
                print("\n🔧 Available Tools:")
                for tool in agent.get_tool_info():
                    print(f"\n   {tool['name']}:")
                    print(f"   {tool['description'][:100]}...")
                continue
            
            print("\n🔍 Processing...\n")
            result = agent.query(question)
            
            print("\n" + "=" * 60)
            print("📝 ANSWER:")
            print("=" * 60)
            print(result["answer"])
            
            if result["tools_used"]:
                print(f"\n🔧 Tools used: {', '.join(result['tools_used'])}")
            
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye! 👋")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Please try again with a different question.")


def main():
    """Main entry point."""
    print("🚀 Starting IMRAG Demo...")
    print()
    
    # Check prerequisites
    if not check_environment():
        print("\n⚠️  Please set up environment variables first.")
        print("   Copy .env.example to .env and add your GROQ_API_KEY")
        return
    
    # Vector DB check is optional for demo (tools have mock data)
    check_vector_db()
    
    # Show API mode (mock vs live)
    check_api_mode()
    
    # Run demo
    run_demo()


if __name__ == "__main__":
    main()
