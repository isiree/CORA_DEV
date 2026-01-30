"""
CLI tool for managing organization credentials
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.security.credential_manager import get_credential_manager
import argparse

def add_org(args):
    """Add a new organization with encrypted credentials"""
    cred_manager = get_credential_manager()
    
    try:
        org = cred_manager.store_credentials(
            org_name=args.org_name,
            org_code=args.org_code,
            tenant_id=args.tenant_id,
            client_id=args.client_id,
            client_secret=args.client_secret,
            contact_email=args.email
        )
        print(f"\n✅ Successfully added organization: {org.org_name}")
        print(f"   Organization Code: {org.org_code}")
        print(f"   Use this code when logging in")
    except Exception as e:
        print(f"\n❌ Error: {e}")

def list_orgs(args):
    """List all organizations"""
    cred_manager = get_credential_manager()
    orgs = cred_manager.list_organizations()
    
    if not orgs:
        print("\nNo organizations found.")
        return
    
    print(f"\n{'='*70}")
    print(f"{'ID':<5} {'Organization Name':<25} {'Code':<15} {'Created':<20}")
    print(f"{'='*70}")
    
    for org in orgs:
        print(f"{org['id']:<5} {org['org_name']:<25} {org['org_code']:<15} {org['created_at']:<20}")
    
    print(f"{'='*70}\n")

def delete_org(args):
    """Delete an organization's credentials"""
    cred_manager = get_credential_manager()
    
    confirm = input(f"⚠️ Are you sure you want to delete credentials for '{args.org_code}'? (yes/no): ")
    if confirm.lower() != 'yes':
        print("❌ Cancelled.")
        return
    
    success = cred_manager.delete_credentials(args.org_code)
    if success:
        print(f"✅ Deleted credentials for: {args.org_code}")
    else:
        print(f"❌ Failed to delete credentials")

def main():
    parser = argparse.ArgumentParser(description="Manage organization credentials")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Add organization
    add_parser = subparsers.add_parser('add', help='Add a new organization')
    add_parser.add_argument('--org-name', required=True, help='Organization name')
    add_parser.add_argument('--org-code', required=True, help='Unique organization code')
    add_parser.add_argument('--tenant-id', required=True, help='Azure tenant ID')
    add_parser.add_argument('--client-id', required=True, help='Azure client ID')
    add_parser.add_argument('--client-secret', required=True, help='Azure client secret')
    add_parser.add_argument('--email', help='Contact email')
    add_parser.set_defaults(func=add_org)
    
    # List organizations
    list_parser = subparsers.add_parser('list', help='List all organizations')
    list_parser.set_defaults(func=list_orgs)
    
    # Delete organization
    del_parser = subparsers.add_parser('delete', help='Delete organization credentials')
    del_parser.add_argument('org_code', help='Organization code to delete')
    del_parser.set_defaults(func=delete_org)
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
