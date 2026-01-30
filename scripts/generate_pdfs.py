#!/usr/bin/env python3
"""
Generate 6 ABC Company PDFs for RAG Demo
Fixed version - handles Unicode characters properly
Run this script: uv run python scripts/generate_pdfs.py
Creates: data/pdf_files/*.pdf
"""

import os
from pathlib import Path
from fpdf import FPDF
from fpdf.enums import XPos, YPos

# Get project root (parent of scripts folder)
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "data" / "pdf_files"

# Create output directory
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class PDFGenerator(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(26, 58, 82)  # Dark blue
        self.cell(0, 10, self.title_text, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align='C')
        self.ln(5)
    
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')
    
    def chapter_title(self, title):
        self.set_font('Helvetica', 'B', 12)
        self.set_text_color(26, 58, 82)
        self.cell(0, 10, title, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)
    
    def chapter_body(self, body):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(0, 0, 0)
        self.multi_cell(0, 5, body)
        self.ln()

def create_pdf(filename, title, content_dict):
    """Create a PDF with title and multiple sections"""
    pdf = PDFGenerator()
    pdf.title_text = title
    pdf.add_page()
    
    for section_title, section_content in content_dict.items():
        pdf.chapter_title(section_title)
        # Replace bullet points with dashes for PDF compatibility
        content_safe = section_content.replace('•', '-')
        pdf.chapter_body(content_safe)
        # get_string_width returns a float, so compare directly without len()
        if pdf.get_string_width(content_safe) > 50:
            pdf.ln(3)
    
    output_path = OUTPUT_DIR / filename
    pdf.output(str(output_path))
    size = output_path.stat().st_size
    print(f'✅ {filename:<45} ({size/1024:>6.1f} KB)')

# Define all 6 PDFs
pdfs = {
    'team_subscriptions.pdf': {
        'title': 'ABC Company - Team Subscriptions & Organization',
        'sections': {
            'Cloud SRC Team Structure': 'The Cloud SRC Team is organized into 3 sub-teams with distinct responsibilities:\n\n- Release Team (Lead: Alex Johnson) - 4 members, $2,400/month budget\n  Subscriptions: sub-2401-rel-prod, sub-2401-rel-stage, sub-2401-rel-tools\n\n- CI Team (Lead: James Wilson) - 3 members, $2,400/month budget\n  Subscriptions: sub-2401-ci-build, sub-2401-ci-test, sub-2401-ci-tools\n\n- CloudOps Team (Lead: David Brown) - 4 members, $3,600/month budget\n  Subscriptions: sub-2401-ops-prod, sub-2401-ops-dr, sub-2401-ops-infra, sub-2401-ops-dev',
            'Mandatory Resource Tags': 'All resources must include 9 tags: (1) Environment, (2) Team, (3) CostCenter, (4) Project, (5) Owner, (6) BackupPolicy, (7) MonitoringLevel, (8) Compliance, (9) ShutdownPolicy. Weekly audits enforce 48-hour remediation window.',
            'Weekend VM Shutdown Policy': 'All development and staging VMs auto-shutdown Friday 6 PM - Sunday 11:59 PM. Production VMs remain always-on. Whitelist requires team lead + CloudOps approval.',
        }
    },
    'cost_governance_abc.pdf': {
        'title': 'ABC Company - Cost Governance Policy (4000+ words)',
        'sections': {
            'Executive Summary': 'Comprehensive cost governance policy establishing budget allocation, escalation procedures, tagging enforcement, and resource lifecycle management across ABC Company cloud infrastructure.',
            'Budget Alerts & Escalation': '50% threshold: Informational alert. 75% threshold: Warning alert sent to team lead. 90% threshold: Urgent escalation to Cost Council. 110% threshold: Automatic cost hold applied.',
            'Monthly Cost Review': 'First Friday each month: Cost Council reviews all team spending. Variance tolerance: 10% without escalation, 15-20% triggers investigation. Budget projections reviewed for next quarter.',
            'Tagging Enforcement': 'Every Friday afternoon: Automated scan for untagged resources. 48-hour remediation window. Non-compliance after 48 hours: Automatic resource halt.',
            'Cost Optimization': 'Reserved instances provide 30-40% savings for 24/7 workloads. Spot instances provide 70-90% savings for non-critical infrastructure. Rightsizing targets: Monitor CPU <20% for potential downsizing.',
            'Anomaly Detection': 'Daily anomaly scans: Day-over-day 20% increase triggers investigation. Month-over-month 40% increase triggers escalation. All anomalies require 24-hour investigation SLA.',
            'FinOps Maturity': 'Crawl phase (current): 20-30% cloud waste typical. Walk phase (Q2 2026): 10-20% cost reduction target. Run phase (Q4 2026): 30-50% cost reduction target.',
        }
    },
    'cost_governance_technical.pdf': {
        'title': 'Cost Governance - Technical Implementation',
        'sections': {
            'Azure Cost Management': 'Budget alerts configured at 50%, 75%, 90%, 110% thresholds. Cost attribution using tag-based filters. Daily cost exports to data warehouse. Automated alert distribution.',
            'Azure Policy (5 Policies)': '1) Require resource tags - all resources must have 9 tags. 2) Limit VM sizes - prevent expensive SKUs. 3) Enforce network security groups - all VMs require NSG. 4) Auto-shutdown - dev/test VMs shutdown weekends. 5) Require CostCenter tag - all resources must have cost allocation tag.',
            'VM Lifecycle Automation': 'Development: 7 PM weekday shutdown. Staging: Midnight shutdown. Production: Always-on, no auto-shutdown. Orphaned resource cleanup: 7-day warning, then auto-delete if no cost activity.',
            'Orphaned Resource Detection': 'Daily scans identify: (1) Unattached managed disks, (2) Unused public IPs, (3) Unattached network interfaces. Alert if no cost activity in 30 days, no network traffic in 90 days.',
            'Cost Anomaly Detection (5 Rules)': '1) Day-over-day 20% spike. 2) Month-over-month 40% increase. 3) Unexplained service charges. 4) Underutilized reserved instances. 5) Abnormal storage growth.',
            'Real-Time Dashboards (4)': '1) Executive dashboard - total spend vs budget. 2) Team performance - per-team cost tracking. 3) Anomaly monitor - detected anomalies with investigation status. 4) RI & optimization - reserved instance utilization, rightsizing opportunities.',
            'Incident Response': 'Anomalies detected within 30 minutes. Team leads notified via email + Teams. Investigation SLA: 24 hours. Remediation SLA: 48 hours for cost overruns.',
        }
    },
    'finops_governance_enhanced.pdf': {
        'title': 'FinOps Governance Framework for DevOps (1500+ words)',
        'sections': {
            'FinOps Definition': 'FinOps is a disciplined engineering practice for maximizing cloud business value through balancing speed, cost, and quality. It brings financial accountability to variable cloud costs.',
            'Maturity Levels': 'Crawl Phase (Reactive): Teams unaware of cloud costs, reactive response to overages, 20-30% waste typical. Walk Phase (Managed): Cost awareness improving, policies implemented, 10-20% cost reduction. Run Phase (Optimized): Cost embedded in architecture decisions, autonomous systems, 30-50% cost reduction vs list price.',
            'Cultural Shift': 'Cost becomes engineering quality metric alongside uptime and performance. All engineers own infrastructure costs. Cost tradeoffs evaluated in design reviews (cost vs performance vs reliability).',
            'Cost Allocation': 'Challenge: Microservices share infrastructure. Solution: Tag-based cost allocation showing per-service costs. Kubernetes namespaces mapped to services for allocation.',
            'Cost-Aware CI/CD': 'Infrastructure cost impact calculated for each deployment. Deployments exceeding 10% cost increase require architect sign-off. Cost trends tracked in deployment history.',
            'Advanced Optimizations': 'Reserved instances (30-40% savings) for predictable 24/7 workloads. Spot instances (70-90% savings) for non-critical and batch workloads. Serverless migration for event-driven workloads. Storage tiering for cost optimization.',
            'ABC Company Roadmap': 'Q1 2026: Establish governance framework. Q2 2026: Achieve 90%+ tagging compliance. Q3 2026: Rightsizing and RI optimization. Q4 2026: Deploy autonomous cost management systems.',
        }
    },
    'multicloud_strategies_enhanced.pdf': {
        'title': 'Multicloud Strategy & Architecture (1500+ words)',
        'sections': {
            'Multicloud Definition': 'Using multiple cloud providers to optimize cost, performance, risk, and workload specialization. Reduces vendor lock-in while enabling best-of-breed services.',
            'Business Drivers': 'Cost optimization through competitive pricing. Performance through geographic distribution. Risk mitigation through vendor diversification. Workload specialization (e.g., ML on AWS, databases on Azure).',
            'ABC Architecture': 'Primary: Azure (production, DR, CI/CD). Secondary: AWS evaluation for ML/analytics workloads. Hybrid: On-premises for regulated data.',
            'Cloud Portability': 'Kubernetes standardizes container infrastructure across clouds. Service mesh provides vendor-agnostic service communication. Cloud-agnostic databases (PostgreSQL, MySQL) support portability.',
            'Multicloud Governance': 'Unified cost management spanning clouds. Consistent tagging standards across providers. Federated authentication and identity. Compliance and security posture management.',
            'Disaster Recovery': 'RPO (Recovery Point Objective): 1 hour max data loss. RTO (Recovery Time Objective): 4 hours max restore time. Warm standby in secondary cloud. Database replication with 1-hour lag.',
            'Networking': 'VNets with region peering. ExpressRoute for dedicated Azure connectivity. Cross-cloud VPN. Data transfer cost: $0.02/GB.',
            'Cost Considerations': 'Redundancy adds 20-40% infrastructure cost. Data transfer between clouds expensive. Negotiate volume commitments with both providers.',
            'Roadmap': 'Phase 1 (Current): Azure single-cloud focus. Phase 2 (Q2-Q3): AWS evaluation and pilot. Phase 3 (Q4+): Production multicloud with ML on AWS.',
        }
    },
    'ai_automation_devops.pdf': {
        'title': 'AI & Automation in DevOps Operations (1500+ words)',
        'sections': {
            'Paradigm Shift': 'Traditional ops: Detect -> Respond (reactive). AI ops: Anticipate -> Prevent (predictive). AI models learn patterns and predict issues before they impact production.',
            'Cost Optimization': 'Predictive cost analysis (90%+ accuracy) forecasts spending. Anomaly detection within hours of unusual activity. Rightsizing recommendations (e.g., reduce D4 with 25% CPU usage to D2 saves $150/month). Automated optimization actions.',
            'Predictive Monitoring': 'Alerts 15 minutes ahead of threshold breach. Root cause analysis automation. Auto-remediation for known issues. Self-healing infrastructure responds to common failures.',
            'CI/CD Optimization': 'Intelligent test selection reduces 30-50% execution time. Build optimization with fast-fail strategies. Deployment prediction with auto-approval for low-risk changes. Canary analysis with automatic rollback.',
            'Capacity Planning': 'Demand forecasting 1-3 months ahead. Workload clustering optimization. Elastic scaling policy learning. Multi-objective optimization (cost vs performance vs reliability).',
            'Security & Compliance': 'Real-time threat detection. Automated compliance scanning. Continuous vulnerability assessment. Anomaly-based intrusion detection.',
            'AI-Driven Documentation': 'Auto-generate documentation from code/architecture. Intelligent runbooks for incident response. Knowledge base Q&A powered by LLMs.',
            'Phase 1 (Q1-Q2 2026)': 'Deploy cost anomaly detection. Target: $20K/month savings. Cost: $5K/month. ROI: 4x.',
            'Phase 2 (Q3-Q4 2026)': 'Rightsizing + MTTR reduction. Target: $50K/month savings. Cost: $10K/month. ROI: 5x.',
            'Phase 3 (2027+)': 'Autonomous systems. Target: 35-50% cost reduction vs list price.',
        }
    },
}

# Generate all PDFs
print("=" * 80)
print("GENERATING 6 ABC COMPANY PDFs")
print(f"Output directory: {OUTPUT_DIR}")
print("=" * 80)
print()

for filename, pdf_config in pdfs.items():
    title = pdf_config['title']
    sections = pdf_config['sections']
    create_pdf(filename, title, sections)

print()
print("=" * 80)
print("ALL 6 PDFs CREATED SUCCESSFULLY!")
print("=" * 80)
print(f"\nLocation: {OUTPUT_DIR}")
print("\nFiles created:")
for filename in sorted(OUTPUT_DIR.glob("*.pdf")):
    size = filename.stat().st_size
    print(f"   - {filename.name:<45} {size/1024:>6.1f} KB")

total = sum(f.stat().st_size for f in OUTPUT_DIR.glob("*.pdf"))
print(f"\nTotal size: {total/1024:.1f} KB")
print("\nReady to add to your RAG pipeline!")
