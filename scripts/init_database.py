"""
Initialize the encrypted credential database
Run this once to set up the database schema
"""
import sys
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.database.connection import init_database
from src.security.encryption import EncryptionService
import os

def main():
    print("="*60)
    print("Database Initialization Script")
    print("="*60)
    
    # Check if encryption key exists
    if not os.getenv("CREDENTIAL_ENCRYPTION_KEY"):
        print("\n⚠️ No encryption key found in environment!")
        print("Generating a new encryption key...\n")
        
        key = EncryptionService.generate_key()
        
        print("🔑 Generated Encryption Key:")
        print(f"   {key}")
        print("\n⚠️ IMPORTANT: Add this to your .env file:")
        print(f'   CREDENTIAL_ENCRYPTION_KEY="{key}"')
        print("\n⚠️ Keep this key SECRET and NEVER commit it to version control!")
        print("="*60)
        
        response = input("\nHave you saved the key to .env? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Please save the encryption key before continuing.")
            return
    
    # Initialize database
    print("\nCreating database tables...")
    init_database()
    
    print("\n✅ Database initialization complete!")
    print(f"📁 Database location: {Path(__file__).parent.parent / 'data' / 'credentials.db'}")

if __name__ == "__main__":
    main()
