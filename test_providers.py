"""Test the cost providers."""
import os
import sys
sys.path.insert(0, ".")

# Load .env file FIRST
from dotenv import load_dotenv
load_dotenv()

# Verify .env loaded
print("=" * 60)
print("ENVIRONMENT CHECK")
print("=" * 60)
print(f"AZURE_SUBSCRIPTION_ID: {os.getenv('AZURE_SUBSCRIPTION_ID', 'NOT SET')}")
print(f"USE_LIVE_DATA: {os.getenv('USE_LIVE_DATA', 'NOT SET')}")

# Test 1: Mock Mode
print("\n" + "=" * 60)
print("TEST 1: Mock Mode")
print("=" * 60)
os.environ["USE_LIVE_DATA"] = "false"

from src.providers import get_cost_provider, is_live_mode
from src.scenarios import build_scenario_run
from src.g import g
from app import _reset_providers as reset_provider
reset_provider()
g.scenario_run = build_scenario_run("scenario_1_vm_destroy")

print(f"Live mode: {is_live_mode()}")
provider = get_cost_provider()
print(f"Provider: {provider.provider_name}")
print(f"Available: {provider.is_available()}")
print(f"Teams: {provider.get_team_keys()}")

result = provider.get_team_spending("release-team")
if result["success"]:
    print(f"\n✅ Release Team:")
    print(f"   Spend: {result['budget']['current_spend']}")
    print(f"   Budget: {result['budget']['monthly_budget']}")
    print(f"   Status: {result['budget']['budget_status']}")
else:
    print(f"❌ Error: {result['error']}")

summary = provider.get_all_teams_summary()
print(f"\n📊 All Teams Summary:")
for team in summary["teams"]:
    print(f"   {team['status']} {team['team']}: {team['spend']}")

# Test 2: Azure Mode
print("\n" + "=" * 60)
print("TEST 2: Azure Mode Check")
print("=" * 60)
os.environ["USE_LIVE_DATA"] = "true"
reset_provider()

print(f"Live mode: {is_live_mode()}")
provider = get_cost_provider()
print(f"Provider: {provider.provider_name}")

if provider.provider_name == "azure":
    print("✅ Connected to Azure!")
    
    # Test actual Azure query
    print("\nTesting Azure subscription costs...")
    result = provider.get_subscription_costs(os.getenv("AZURE_SUBSCRIPTION_ID"), days=7)
    if result["success"]:
        print(f"   Total cost (7 days): {result['total_cost']}")
    else:
        print(f"   Error: {result['error']}")
else:
    print("⚠️ Using mock (Azure not available)")
    print("\nTo enable Azure:")
    print("   1) Run: az login")
    print("   2) Run: pip install azure-identity azure-mgmt-costmanagement")
    print("   3) Verify .env has AZURE_SUBSCRIPTION_ID set")

print("\n✅ All tests completed!")
