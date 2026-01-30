"""
RAG Retriever - ChromaDB wrapper for semantic document search.
Extracts and productionizes the retrieval logic from pdf_loader.ipynb.
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from .cache_manager import get_cache

load_dotenv()


class RAGRetriever:
    """
    Production-grade RAG retriever using ChromaDB.
    
    Features:
    - Semantic similarity search
    - Caching to avoid redundant queries
    - Metadata filtering
    - Distance-to-similarity conversion
    """
    
    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: Optional[str] = None,
        embedding_model: Optional[str] = None,
        use_cache: bool = True
    ):
        """
        Initialize the RAG retriever.
        
        Args:
            persist_dir: ChromaDB persistence directory
            collection_name: Name of the collection
            embedding_model: SentenceTransformer model name
            use_cache: Whether to use caching
        """
        self.persist_dir = persist_dir or os.getenv("CHROMA_PERSIST_DIR", "data/vector_db")
        self.collection_name = collection_name or os.getenv("COLLECTION_NAME", "abc_company_docs")
        self.embedding_model_name = embedding_model or os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.use_cache = use_cache
        
        self._client: Optional[chromadb.ClientAPI] = None
        self._collection: Optional[chromadb.Collection] = None
        self._embedding_model: Optional[SentenceTransformer] = None
        self._cache = get_cache() if use_cache else None
    
    @property
    def client(self) -> chromadb.ClientAPI:
        """Lazy-load ChromaDB client."""
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False)
            )
        return self._client
    
    @property
    def collection(self) -> chromadb.Collection:
        """Lazy-load collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
        return self._collection
    
    @property
    def embedding_model(self) -> SentenceTransformer:
        """Lazy-load embedding model."""
        if self._embedding_model is None:
            # Use local cache directory for models
            cache_dir = Path("models")
            cache_dir.mkdir(exist_ok=True)
            self._embedding_model = SentenceTransformer(
                self.embedding_model_name,
                cache_folder=str(cache_dir)
            )
        return self._embedding_model
    
    def _distance_to_similarity(self, distance: float) -> float:
        """Convert cosine distance to similarity score."""
        return 1 - distance
    
    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.0,
        filter_metadata: Optional[dict] = None
    ) -> list[dict]:
        """
        Retrieve relevant documents for a query.
        
        Args:
            query: Search query
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold (0-1)
            filter_metadata: Optional metadata filters
        
        Returns:
            List of results with content, metadata, and similarity scores
        """
        # Check cache first
        if self.use_cache and self._cache:
            cached = self._cache.get(
                "historical",
                query=query,
                top_k=top_k,
                min_similarity=min_similarity,
                filter_metadata=filter_metadata
            )
            if cached is not None:
                return cached
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode(query).tolist()
        
        # Build query parameters
        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"]
        }
        
        if filter_metadata:
            query_params["where"] = filter_metadata
        
        # Query ChromaDB
        results = self.collection.query(**query_params)
        
        # Process results
        processed_results = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i]
                similarity = self._distance_to_similarity(distance)
                
                if similarity >= min_similarity:
                    processed_results.append({
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "similarity": round(similarity, 4),
                        "distance": round(distance, 4)
                    })
        
        # Cache results
        if self.use_cache and self._cache:
            self._cache.set(
                "historical",
                processed_results,
                query=query,
                top_k=top_k,
                min_similarity=min_similarity,
                filter_metadata=filter_metadata
            )
        
        return processed_results
    
    def get_collection_stats(self) -> dict:
        """Get statistics about the collection."""
        count = self.collection.count()
        return {
            "collection_name": self.collection_name,
            "document_count": count,
            "persist_dir": self.persist_dir,
            "embedding_model": self.embedding_model_name
        }
    
    def add_documents(
        self,
        documents: list[str],
        metadatas: Optional[list[dict]] = None,
        ids: Optional[list[str]] = None
    ) -> None:
        """
        Add documents to the collection.
        
        Args:
            documents: List of document texts
            metadatas: Optional list of metadata dicts
            ids: Optional list of document IDs
        """
        if not ids:
            # Generate IDs based on existing count
            start_id = self.collection.count()
            ids = [f"doc_{start_id + i}" for i in range(len(documents))]
        
        if not metadatas:
            metadatas = [{}] * len(documents)
        
        # Generate embeddings
        embeddings = self.embedding_model.encode(documents).tolist()
        
        # Add to collection
        self.collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
        
        # Clear cache since data changed
        if self.use_cache and self._cache:
            self._cache.clear("historical")


# Singleton instance
_retriever_instance: Optional[RAGRetriever] = None


def get_retriever() -> RAGRetriever:
    """Get or create global retriever instance."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = RAGRetriever()
    return _retriever_instance
