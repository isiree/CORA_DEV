#!/bin/bash
# ============================================
# IMRAG - Local Terraform Helper Script
# For Azure Student accounts (no SPN required)
# 
# Usage:
#   ./scripts/terraform_apply.sh plan
#   ./scripts/terraform_apply.sh apply
#   ./scripts/terraform_apply.sh scale_up
#   ./scripts/terraform_apply.sh scale_down
#   ./scripts/terraform_apply.sh destroy
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="$SCRIPT_DIR/../infrastructure/terraform"
ACTION=${1:-plan}
TEAM=${2:-all}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}🔧 IMRAG Terraform Helper${NC}"
echo "========================="
echo -e "Action: ${YELLOW}$ACTION${NC}"
echo -e "Team: ${YELLOW}$TEAM${NC}"
echo ""

cd "$TF_DIR"

# Check Azure login
echo -e "${BLUE}🔐 Checking Azure login...${NC}"
if ! az account show &>/dev/null; then
    echo -e "${YELLOW}Not logged in. Running az login...${NC}"
    az login
fi

SUBSCRIPTION=$(az account show --query name -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)
echo -e "${GREEN}✅ Logged in to: $SUBSCRIPTION${NC}"
echo -e "   Subscription ID: $SUBSCRIPTION_ID"
echo ""

case $ACTION in
    plan)
        echo -e "${BLUE}📋 Running terraform plan...${NC}"
        echo ""
        terraform init
        terraform plan
        echo ""
        echo -e "${GREEN}✅ Plan complete!${NC}"
        ;;
    
    apply)
        echo -e "${BLUE}🚀 Running terraform apply...${NC}"
        echo ""
        terraform init
        terraform apply -auto-approve
        echo ""
        echo -e "${GREEN}✅ Apply complete!${NC}"
        echo ""
        echo -e "${YELLOW}📝 Track this change in GitLab:${NC}"
        echo "   1. Go to: GitLab → CI/CD → Pipelines → Run Pipeline"
        echo "   2. Add variable: ACTION = track_apply"
        echo "   3. Add variable: TEAM = $TEAM"
        echo "   4. Click 'Run Pipeline'"
        ;;
    
    scale_up)
        echo -e "${BLUE}📈 Scaling UP container resources...${NC}"
        echo "   Target: CPU=0.5, Memory=1.0GB"
        echo ""
        terraform init
        terraform apply -auto-approve \
            -var="container_cpu=0.5" \
            -var="container_memory=1.0"
        echo ""
        echo -e "${GREEN}✅ Scale up complete!${NC}"
        echo ""
        echo -e "${YELLOW}📝 Track this change in GitLab:${NC}"
        echo "   1. Go to: GitLab → CI/CD → Pipelines → Run Pipeline"
        echo "   2. Add variable: ACTION = track_scale_up"
        echo "   3. Click 'Run Pipeline'"
        ;;
    
    scale_down)
        echo -e "${BLUE}📉 Scaling DOWN container resources...${NC}"
        echo "   Target: CPU=0.25, Memory=0.5GB"
        echo ""
        terraform init
        terraform apply -auto-approve \
            -var="container_cpu=0.25" \
            -var="container_memory=0.5"
        echo ""
        echo -e "${GREEN}✅ Scale down complete!${NC}"
        echo ""
        echo -e "${YELLOW}📝 Track this change in GitLab:${NC}"
        echo "   1. Go to: GitLab → CI/CD → Pipelines → Run Pipeline"
        echo "   2. Add variable: ACTION = track_scale_down"
        echo "   3. Click 'Run Pipeline'"
        ;;
    
    destroy)
        echo -e "${RED}🗑️ WARNING: This will destroy ALL resources!${NC}"
        echo ""
        read -p "Are you sure you want to continue? (yes/no): " confirm
        if [ "$confirm" == "yes" ]; then
            terraform init
            terraform destroy -auto-approve
            echo ""
            echo -e "${GREEN}✅ Destroy complete!${NC}"
            echo ""
            echo -e "${YELLOW}📝 Track this change in GitLab:${NC}"
            echo "   1. Go to: GitLab → CI/CD → Pipelines → Run Pipeline"
            echo "   2. Add variable: ACTION = track_destroy"
            echo "   3. Click 'Run Pipeline'"
        else
            echo -e "${YELLOW}Cancelled.${NC}"
        fi
        ;;
    
    init)
        echo -e "${BLUE}🔧 Initializing Terraform...${NC}"
        terraform init
        echo ""
        echo -e "${GREEN}✅ Terraform initialized!${NC}"
        ;;
    
    validate)
        echo -e "${BLUE}🔍 Validating Terraform configuration...${NC}"
        terraform init -backend=false
        terraform validate
        terraform fmt -check -diff || true
        echo ""
        echo -e "${GREEN}✅ Validation complete!${NC}"
        ;;
    
    output)
        echo -e "${BLUE}📤 Showing Terraform outputs...${NC}"
        terraform output
        ;;
    
    state)
        echo -e "${BLUE}📋 Listing Terraform state...${NC}"
        terraform state list
        ;;
    
    *)
        echo -e "${RED}Unknown action: $ACTION${NC}"
        echo ""
        echo "Usage: $0 {plan|apply|scale_up|scale_down|destroy|init|validate|output|state} [team]"
        echo ""
        echo "Actions:"
        echo "  plan       - Show planned infrastructure changes"
        echo "  apply      - Apply infrastructure changes"
        echo "  scale_up   - Scale up container resources (CPU=0.5, Memory=1.0GB)"
        echo "  scale_down - Scale down container resources (CPU=0.25, Memory=0.5GB)"
        echo "  destroy    - Destroy all infrastructure"
        echo "  init       - Initialize Terraform"
        echo "  validate   - Validate Terraform configuration"
        echo "  output     - Show Terraform outputs"
        echo "  state      - List resources in state"
        echo ""
        echo "Examples:"
        echo "  $0 plan                # Preview changes"
        echo "  $0 apply               # Deploy infrastructure"
        echo "  $0 scale_up ci-team    # Scale up CI team resources"
        echo "  $0 destroy             # Remove all resources"
        exit 1
        ;;
esac