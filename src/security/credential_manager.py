"""
Credential manager for storing and retrieving encrypted Azure credentials
"""
from typing import Dict, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from ..database.models import Organization, AuditLog
from ..database.connection import get_db
from .encryption import get_encryption_service

class AzureCredentials:
    """Represents decrypted Azure credentials (in-memory only)"""
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
    
    def __repr__(self):
        return f"<AzureCredentials(tenant_id={self.tenant_id[:8]}..., client_id={self.client_id[:8]}...)>"
    
    def to_dict(self) -> Dict[str, str]:
        return {
            'tenant_id': self.tenant_id,
            'client_id': self.client_id,
            'client_secret': self.client_secret
        }

class CredentialManager:
    """
    Manages encrypted credential storage and retrieval
    """
    
    def __init__(self):
        self.encryption_service = get_encryption_service()
    
    def store_credentials(
        self,
        org_name: str,
        org_code: str,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        contact_email: Optional[str] = None,
        subscription_ids: Optional[List[str]] = None
    ) -> Organization:
        """
        Store encrypted Azure credentials for an organization
        
        Args:
            org_name: Organization name (e.g., "Acme Corporation")
            org_code: Unique code (e.g., "acme")
            tenant_id: Azure AD tenant ID
            client_id: Azure service principal client ID
            client_secret: Azure service principal client secret
            contact_email: Optional contact email
            subscription_ids: Optional list of subscription IDs
            
        Returns:
            Created Organization object
        """
        session = get_db()
        
        try:
            # Check if org already exists
            existing = session.query(Organization).filter_by(org_code=org_code).first()
            if existing:
                raise ValueError(f"Organization with code '{org_code}' already exists")
            
            # Encrypt credentials
            encrypted_tenant = self.encryption_service.encrypt(tenant_id)
            encrypted_client = self.encryption_service.encrypt(client_id)
            encrypted_secret = self.encryption_service.encrypt(client_secret)
            
            # Create organization
            org = Organization(
                org_name=org_name,
                org_code=org_code,
                encrypted_tenant_id=encrypted_tenant,
                encrypted_client_id=encrypted_client,
                encrypted_client_secret=encrypted_secret,
                contact_email=contact_email,
                subscription_ids=str(subscription_ids) if subscription_ids else None
            )
            
            session.add(org)
            session.commit()
            
            # Audit log
            self._log_audit(session, org.id, None, "CREDENTIAL_STORED", f"Stored credentials for {org_name}")
            
            print(f"✅ Stored encrypted credentials for: {org_name} ({org_code})")
            return org
            
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
    
    def get_credentials(self, org_code: str) -> Optional[AzureCredentials]:
        """
        Retrieve and decrypt Azure credentials for an organization
        
        Args:
            org_code: Organization code
            
        Returns:
            AzureCredentials object or None if not found
        """
        session = get_db()
        
        try:
            # Fetch organization
            org = session.query(Organization).filter_by(org_code=org_code, is_active=True).first()
            
            if not org:
                print(f"⚠️ No active organization found with code: {org_code}")
                return None
            
            # Decrypt credentials
            tenant_id = self.encryption_service.decrypt(org.encrypted_tenant_id)
            client_id = self.encryption_service.decrypt(org.encrypted_client_id)
            client_secret = self.encryption_service.decrypt(org.encrypted_client_secret)
            
            # Audit log
            self._log_audit(session, org.id, None, "CREDENTIAL_RETRIEVED", f"Retrieved credentials for {org.org_name}")
            
            print(f"🔓 Retrieved credentials for: {org.org_name}")
            
            return AzureCredentials(tenant_id, client_id, client_secret)
            
        except Exception as e:
            print(f"❌ Error retrieving credentials: {e}")
            return None
        finally:
            session.close()
    
    def update_credentials(
        self,
        org_code: str,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ) -> bool:
        """
        Update credentials for an organization
        
        Args:
            org_code: Organization code
            tenant_id: New tenant ID (optional)
            client_id: New client ID (optional)
            client_secret: New client secret (optional)
            
        Returns:
            True if successful, False otherwise
        """
        session = get_db()
        
        try:
            org = session.query(Organization).filter_by(org_code=org_code).first()
            
            if not org:
                print(f"⚠️ Organization not found: {org_code}")
                return False
            
            # Update only provided fields
            if tenant_id:
                org.encrypted_tenant_id = self.encryption_service.encrypt(tenant_id)
            if client_id:
                org.encrypted_client_id = self.encryption_service.encrypt(client_id)
            if client_secret:
                org.encrypted_client_secret = self.encryption_service.encrypt(client_secret)
            
            org.updated_at = datetime.utcnow()
            session.commit()
            
            # Audit log
            self._log_audit(session, org.id, None, "CREDENTIAL_UPDATED", f"Updated credentials for {org.org_name}")
            
            print(f"✅ Updated credentials for: {org.org_name}")
            return True
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error updating credentials: {e}")
            return False
        finally:
            session.close()
    
    def delete_credentials(self, org_code: str) -> bool:
        """
        Delete (deactivate) credentials for an organization
        
        Args:
            org_code: Organization code
            
        Returns:
            True if successful
        """
        session = get_db()
        
        try:
            org = session.query(Organization).filter_by(org_code=org_code).first()
            
            if not org:
                print(f"⚠️ Organization not found: {org_code}")
                return False
            
            # Soft delete (mark as inactive)
            org.is_active = False
            session.commit()
            
            # Audit log
            self._log_audit(session, org.id, None, "CREDENTIAL_DELETED", f"Deleted credentials for {org.org_name}")
            
            print(f"✅ Deleted credentials for: {org.org_name}")
            return True
            
        except Exception as e:
            session.rollback()
            print(f"❌ Error deleting credentials: {e}")
            return False
        finally:
            session.close()
    
    def list_organizations(self) -> List[Dict]:
        """
        List all organizations (without decrypting credentials)
        
        Returns:
            List of organization info dicts
        """
        session = get_db()
        
        try:
            orgs = session.query(Organization).filter_by(is_active=True).all()
            
            return [
                {
                    'id': org.id,
                    'org_name': org.org_name,
                    'org_code': org.org_code,
                    'contact_email': org.contact_email,
                    'created_at': org.created_at.isoformat(),
                    'is_active': org.is_active
                }
                for org in orgs
            ]
            
        finally:
            session.close()
    
    def _log_audit(self, session: Session, org_id: int, user_id: Optional[int], action: str, details: str):
        """Log credential access for auditing"""
        log = AuditLog(
            org_id=org_id,
            user_id=user_id,
            action=action,
            details=details
        )
        session.add(log)
        session.commit()

# Singleton instance
_credential_manager: Optional[CredentialManager] = None

def get_credential_manager() -> CredentialManager:
    """Get or create the global credential manager instance"""
    global _credential_manager
    
    if _credential_manager is None:
        _credential_manager = CredentialManager()
    
    return _credential_manager
