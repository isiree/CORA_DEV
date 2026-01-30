"""
Encryption service for securing credentials at rest
Uses Fernet (AES-256) symmetric encryption
"""
from cryptography.fernet import Fernet
import os
import base64
from typing import Optional

class EncryptionService:
    """
    Handles encryption and decryption of sensitive data
    """
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption service
        
        Args:
            encryption_key: Base64-encoded Fernet key. If None, loads from env var.
        """
        if encryption_key is None:
            encryption_key = os.getenv("CREDENTIAL_ENCRYPTION_KEY")
        
        if not encryption_key:
            raise ValueError(
                "Encryption key not found. Set CREDENTIAL_ENCRYPTION_KEY environment variable. "
                "Generate one with: from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
            )
        
        self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a string
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            raise ValueError("Cannot encrypt empty string")
        
        encrypted_bytes = self.cipher.encrypt(plaintext.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        Decrypt an encrypted string
        
        Args:
            encrypted_text: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
        """
        if not encrypted_text:
            raise ValueError("Cannot decrypt empty string")
        
        decrypted_bytes = self.cipher.decrypt(encrypted_text.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    
    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key
        
        Returns:
            Base64-encoded encryption key (store in .env)
        """
        key = Fernet.generate_key()
        return key.decode('utf-8')

# Singleton instance
_encryption_service: Optional[EncryptionService] = None

def get_encryption_service() -> EncryptionService:
    """Get or create the global encryption service instance"""
    global _encryption_service
    
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    
    return _encryption_service
