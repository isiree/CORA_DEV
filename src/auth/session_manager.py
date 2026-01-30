"""
Session management for tracking which organization a user belongs to
"""
from typing import Optional
from ..security.credential_manager import AzureCredentials, get_credential_manager

class UserSession:
    """
    Represents a user's session with their organization context
    """
    
    def __init__(self):
        self.org_code: Optional[str] = None
        self.org_name: Optional[str] = None
        self.username: Optional[str] = None
        self._cached_credentials: Optional[AzureCredentials] = None
    
    def login(self, org_code: str, org_name: str = "", username: str = ""):
        """
        Set the current organization context (simulates user login)
        
        Args:
            org_code: Organization code to set context for
            org_name: Organization display name
            username: User's username (optional for FYP)
        """
        self.org_code = org_code
        self.org_name = org_name or org_code
        self.username = username or f"user@{org_code}"
        self._cached_credentials = None
        
        print(f"✅ Session started for {self.username} @ {self.org_name}")
    
    def logout(self):
        """Clear session and cached credentials"""
        self.org_code = None
        self.org_name = None
        self.username = None
        self._cached_credentials = None
        
        print("👋 Session ended")
    
    def get_credentials(self) -> Optional[AzureCredentials]:
        """
        Get Azure credentials for the current organization
        Caches credentials for the session duration
        
        Returns:
            AzureCredentials or None if no session
        """
        if not self.org_code:
            print("⚠️ No active session. Please login first.")
            return None
        
        # Return cached credentials if available
        if self._cached_credentials:
            return self._cached_credentials
        
        # Retrieve from database
        cred_manager = get_credential_manager()
        self._cached_credentials = cred_manager.get_credentials(self.org_code)
        
        return self._cached_credentials
    
    def is_authenticated(self) -> bool:
        """Check if user has an active session"""
        return self.org_code is not None
    
    def __repr__(self):
        if self.is_authenticated():
            return f"<UserSession(user={self.username}, org={self.org_name})>"
        return "<UserSession(not authenticated)>"

# Global session instance (in production, use proper session management per user)
_current_session = UserSession()

def get_current_session() -> UserSession:
    """Get the current user session"""
    return _current_session
