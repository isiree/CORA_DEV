#!/usr/bin/env python3
"""
Set up the vector database from PDFs.
Use --fresh to delete existing data and start over.
Default behavior: Add new PDFs to existing database.

Usage:
    uv run python scripts/setup_vector_db.py          # Add new PDFs only
    uv run python scripts/setup_vector_db.py --fresh  # Delete and recreate all
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import fitz  # PyMuPDF


def get_existing_sources(collection) -> set:
    """Get set of PDF filenames already in the collection."""
    try:
        # Get all metadata to find existing sources
        results = collection.get(include=["metadatas"])
        if results and results["metadatas"]:
            return {m.get("source", "") for m in results["metadatas"] if m}
    except Exception:
        pass
    return set()


def main(fresh_start: bool = False):
    print("🔧 Setting up Vector Database...")
    print("=" * 50)
    
    # Paths
    pdf_dir = project_root / "data" / "pdf_files"
    db_dir = project_root / "data" / "vector_db"
    
    # Check PDFs exist
    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"❌ No PDFs found in {pdf_dir}")
        print("   Run: uv run python scripts/generate_pdfs.py")
        return False
    
    print(f"📄 Found {len(pdf_files)} PDFs in {pdf_dir}")
    
    # Initialize embedding model
    print("\n🧠 Loading embedding model...")
    model_cache = project_root / "models"
    model_cache.mkdir(exist_ok=True)
    model = SentenceTransformer(
        os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        cache_folder=str(model_cache)
    )
    print("   Model loaded!")
    
    # Initialize ChromaDB
    print("\n🗄️  Initializing ChromaDB...")
    db_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(db_dir),
        settings=Settings(anonymized_telemetry=False)
    )
    
    collection_name = os.getenv("COLLECTION_NAME", "abc_company_docs")
    
    if fresh_start:
        # Delete existing collection to start fresh
        try:
            client.delete_collection(collection_name)
            print(f"   ⚠️  Deleted existing collection: {collection_name}")
        except Exception:
            pass
        collection = client.create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        existing_sources = set()
    else:
        # Get or create collection (preserves existing data)
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        existing_sources = get_existing_sources(collection)
        print(f"   Existing documents: {collection.count()}")
        if existing_sources:
            print(f"   Already indexed: {', '.join(sorted(existing_sources))}")
    
    # Filter to only new PDFs
    new_pdf_files = [p for p in pdf_files if p.name not in existing_sources]
    
    if not new_pdf_files:
        print("\n✅ All PDFs are already indexed. Nothing to do!")
        print(f"   Use --fresh flag to reindex everything.")
        return True
    
    print(f"\n📖 Processing {len(new_pdf_files)} new PDFs...")
    all_chunks = []
    all_metadatas = []
    all_ids = []
    
    for pdf_path in sorted(new_pdf_files):
        print(f"   Processing: {pdf_path.name}...", end=" ")
        try:
            doc = fitz.open(pdf_path)
            chunk_count = 0
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                
                # Simple chunking by paragraphs (non-empty, >50 chars)
                paragraphs = [
                    p.strip() 
                    for p in text.split("\n\n") 
                    if p.strip() and len(p.strip()) > 50
                ]
                
                for i, chunk in enumerate(paragraphs):
                    chunk_id = f"{pdf_path.stem}_p{page_num}_c{i}"
                    all_chunks.append(chunk)
                    all_metadatas.append({
                        "source": pdf_path.name,
                        "page": page_num,
                        "chunk_index": i
                    })
                    all_ids.append(chunk_id)
                    chunk_count += 1
            
            doc.close()
            print(f"✅ {chunk_count} chunks")
            
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print(f"\n📊 New chunks to add: {len(all_chunks)}")
    
    if not all_chunks:
        print("⚠️  No new text chunks extracted!")
        return True
    
    # Generate embeddings
    print("\n🔢 Generating embeddings...")
    embeddings = model.encode(
        all_chunks,
        show_progress_bar=True,
        batch_size=32
    ).tolist()
    
    # Add to ChromaDB in batches
    print("\n💾 Adding to ChromaDB...")
    batch_size = 100
    for i in range(0, len(all_chunks), batch_size):
        end = min(i + batch_size, len(all_chunks))
        collection.add(
            documents=all_chunks[i:end],
            embeddings=embeddings[i:end],
            metadatas=all_metadatas[i:end],
            ids=all_ids[i:end]
        )
        print(f"   Added batch {i//batch_size + 1}/{(len(all_chunks)-1)//batch_size + 1}")
    
    # Verify
    final_count = collection.count()
    print("\n" + "=" * 50)
    print(f"✅ Vector database updated successfully!")
    print(f"   📁 Location: {db_dir}")
    print(f"   📊 Total documents: {final_count}")
    print(f"   🏷️  Collection: {collection_name}")
    print("\n🚀 You can now run: uv run python main.py")
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set up vector database from PDFs")
    parser.add_argument(
        "--fresh", 
        action="store_true", 
        help="Delete existing data and reindex all PDFs"
    )
    args = parser.parse_args()
    
    success = main(fresh_start=args.fresh)
    sys.exit(0 if success else 1)
