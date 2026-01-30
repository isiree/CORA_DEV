"""
Database models for encrypted credential storage
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Organization(Base):
    """Represents a company/organization using the system"""
    __tablename__ = 'organizations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    org_name = Column(String(255), unique=True, nullable=False)
    org_code = Column(String(50), unique=True, nullable=False)  # e.g., "company-a"
    
    # Encrypted Azure credentials (stored as encrypted strings)
    encrypted_tenant_id = Column(Text, nullable=False)
    encrypted_client_id = Column(Text, nullable=False)
    encrypted_client_secret = Column(Text, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Optional: additional info
    contact_email = Column(String(255), nullable=True)
    subscription_ids = Column(Text, nullable=True)  # JSON list of subscription IDs
    
    def __repr__(self):
        return f"<Organization(id={self.id}, org_name='{self.org_name}', org_code='{self.org_code}')>"

class User(Base):
    """User accounts for the system (optional - for future authentication)"""
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    org_id = Column(Integer, nullable=False)  # Foreign key to Organization
    
    # For demo: simple password hash (in production, use proper auth)
    password_hash = Column(String(255), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', org_id={self.org_id})>"

class AuditLog(Base):
    """Log all credential access for security auditing"""
    __tablename__ = 'audit_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    org_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=True)
    action = Column(String(100), nullable=False)  # e.g., "CREDENTIAL_RETRIEVED", "CREDENTIAL_STORED"
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    ip_address = Column(String(50), nullable=True)
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, org_id={self.org_id}, action='{self.action}')>"
