#!/usr/bin/env python3
"""
Set up the vector database from mixed document sources.
Use --fresh to delete existing data and start over.
Default behavior: Add only new source documents to existing database.

Supported file types:
    - .pdf
    - .md / .markdown
    - .txt
    - .docx

Usage:
    uv run python scripts/setup_vector_db.py          # Add new docs only
    uv run python scripts/setup_vector_db.py --fresh  # Delete and reindex all docs
"""

import os
import sys
import argparse
import hashlib
import re
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import fitz  # PyMuPDF

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt", ".docx"}
MIN_CHUNK_CHARS = 50
FALLBACK_WORD_CHUNK_SIZE = 180
FALLBACK_WORD_CHUNK_OVERLAP = 30
DEFAULT_SOURCE_DIRS = ["data/docs", "data/pdf_files", "data/text_files"]
SKIP_DIR_NAMES = {"vector_db", "vector_store", "cache", "__pycache__"}


def get_existing_sources(collection) -> set:
    """Get set of source identifiers already in the collection."""
    try:
        # Get all metadata to find existing sources
        results = collection.get(include=["metadatas"])
        if results and results["metadatas"]:
            return {m.get("source", "") for m in results["metadatas"] if m}
    except Exception:
        pass
    return set()


def get_source_directories() -> list[Path]:
    """
    Resolve source directories from env var RAG_SOURCE_DIRS or defaults.

    RAG_SOURCE_DIRS example:
        "data/docs,data/pdf_files,data/text_files"
    """
    raw = os.getenv("RAG_SOURCE_DIRS", ",".join(DEFAULT_SOURCE_DIRS))
    dirs: list[Path] = []
    for part in raw.split(","):
        candidate = (project_root / part.strip()).resolve()
        if candidate.exists() and candidate.is_dir():
            dirs.append(candidate)
    return dirs


def collect_source_files(source_dirs: list[Path]) -> list[Path]:
    """Collect supported files recursively from configured source directories."""
    files: list[Path] = []

    for source_dir in source_dirs:
        for path in source_dir.rglob("*"):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix.lower() in SUPPORTED_EXTENSIONS:
                files.append(path)

    return sorted(files)


def normalize_whitespace(text: str) -> str:
    """Normalize whitespace while preserving paragraph boundaries."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def chunk_text(text: str) -> list[str]:
    """
    Chunk text by paragraphs first, then fallback to word chunks for dense content.
    """
    cleaned = normalize_whitespace(text)
    if not cleaned:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    chunks = [p for p in paragraphs if len(p) >= MIN_CHUNK_CHARS]
    if chunks:
        return chunks

    words = cleaned.split()
    if not words:
        return []

    chunks = []
    step = max(FALLBACK_WORD_CHUNK_SIZE - FALLBACK_WORD_CHUNK_OVERLAP, 1)
    for i in range(0, len(words), step):
        chunk = " ".join(words[i : i + FALLBACK_WORD_CHUNK_SIZE]).strip()
        if len(chunk) >= MIN_CHUNK_CHARS:
            chunks.append(chunk)
        if i + FALLBACK_WORD_CHUNK_SIZE >= len(words):
            break
    return chunks


def extract_docx_text(docx_path: Path) -> str:
    """Extract plain text from .docx file without external dependencies."""
    with ZipFile(docx_path) as zf:
        xml_bytes = zf.read("word/document.xml")

    root = ET.fromstring(xml_bytes)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    paragraphs: list[str] = []
    for para in root.findall(".//w:p", ns):
        texts = [node.text for node in para.findall(".//w:t", ns) if node.text]
        merged = "".join(texts).strip()
        if merged:
            paragraphs.append(merged)

    return "\n\n".join(paragraphs)


def build_chunk_id(source: str, page: int | None, chunk_index: int) -> str:
    """Build deterministic ID for each chunk."""
    token = f"{source}|{page}|{chunk_index}"
    digest = hashlib.sha1(token.encode("utf-8")).hexdigest()[:16]
    return f"doc_{digest}"


def source_identifier(path: Path) -> str:
    """Create stable source path relative to project root."""
    return str(path.resolve().relative_to(project_root.resolve()))


def process_source_file(file_path: Path) -> tuple[list[str], list[dict], list[str]]:
    """
    Process a single file into chunks + metadata + IDs.

    Returns:
        (chunks, metadatas, ids)
    """
    suffix = file_path.suffix.lower()
    source = source_identifier(file_path)

    chunks: list[str] = []
    metadatas: list[dict] = []
    ids: list[str] = []

    if suffix == ".pdf":
        doc = fitz.open(file_path)
        try:
            for page_num in range(len(doc)):
                page_text = doc[page_num].get_text()
                page_chunks = chunk_text(page_text)
                for idx, chunk in enumerate(page_chunks):
                    chunks.append(chunk)
                    metadatas.append(
                        {
                            "source": source,
                            "file_type": suffix.lstrip("."),
                            "page": page_num,
                            "chunk_index": idx,
                        }
                    )
                    ids.append(build_chunk_id(source, page_num, idx))
        finally:
            doc.close()
        return chunks, metadatas, ids

    if suffix in {".md", ".markdown", ".txt"}:
        text = file_path.read_text(encoding="utf-8", errors="ignore")
    elif suffix == ".docx":
        text = extract_docx_text(file_path)
    else:
        return [], [], []

    text_chunks = chunk_text(text)
    for idx, chunk in enumerate(text_chunks):
        chunks.append(chunk)
        metadatas.append(
            {
                "source": source,
                "file_type": suffix.lstrip("."),
                "chunk_index": idx,
            }
        )
        ids.append(build_chunk_id(source, None, idx))

    return chunks, metadatas, ids


def main(fresh_start: bool = False):
    print("🔧 Setting up Vector Database...")
    print("=" * 50)

    # Paths
    db_dir = project_root / "data" / "vector_db"

    # Source files
    source_dirs = get_source_directories()
    if not source_dirs:
        print("❌ No source directories found.")
        print("   Configure RAG_SOURCE_DIRS or create one of:")
        for d in DEFAULT_SOURCE_DIRS:
            print(f"   - {project_root / d}")
        return False

    source_files = collect_source_files(source_dirs)
    if not source_files:
        print("❌ No supported files found.")
        print(f"   Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
        print("   Checked directories:")
        for d in source_dirs:
            print(f"   - {d}")
        return False

    print(f"📁 Source directories ({len(source_dirs)}):")
    for d in source_dirs:
        print(f"   - {d}")
    print(f"📄 Found {len(source_files)} supported files")
    
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
    
    # Filter to only new sources
    new_source_files = [p for p in source_files if source_identifier(p) not in existing_sources]

    if not new_source_files:
        print("\n✅ All source files are already indexed. Nothing to do!")
        print("   Use --fresh flag to reindex everything.")
        return True

    print(f"\n📖 Processing {len(new_source_files)} new files...")
    all_chunks = []
    all_metadatas = []
    all_ids = []

    for source_path in sorted(new_source_files):
        print(f"   Processing: {source_identifier(source_path)}...", end=" ")
        try:
            chunks, metadatas, ids = process_source_file(source_path)
            all_chunks.extend(chunks)
            all_metadatas.extend(metadatas)
            all_ids.extend(ids)
            print(f"✅ {len(chunks)} chunks")
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
    parser = argparse.ArgumentParser(description="Set up vector database from mixed document sources")
    parser.add_argument(
        "--fresh", 
        action="store_true", 
        help="Delete existing data and reindex all supported files"
    )
    args = parser.parse_args()
    
    success = main(fresh_start=args.fresh)
    sys.exit(0 if success else 1)
