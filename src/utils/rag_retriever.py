"""
RAG Retriever - ChromaDB wrapper for semantic document search.
Extracts and productionizes the retrieval logic from pdf_loader.ipynb.
"""

import os
import re
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
    - Hybrid dense + keyword retrieval
    - Heuristic reranking with source diversity
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
        self._keyword_corpus: Optional[list[dict]] = None

        self.hybrid_enabled = os.getenv("RAG_HYBRID_ENABLED", "true").lower() != "false"
        self.candidate_multiplier = max(int(os.getenv("RAG_CANDIDATE_MULTIPLIER", "4")), 2)
        self.max_per_source = max(int(os.getenv("RAG_MAX_RESULTS_PER_SOURCE", "1")), 1)

    _TOKEN_RE = re.compile(r"[a-z0-9]+")
    _SCENARIO_RE = re.compile(r"\bscenario\s+\d+\b", re.IGNORECASE)
    _QUESTION_PREFIXES = (
        "what is the main reason for",
        "what is the main root cause of",
        "what is the root cause of",
        "what is the reason for",
        "what caused",
        "why did",
        "why is",
    )
    
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

    def _normalize_query(self, query: str) -> str:
        """Remove boilerplate phrasing that tends to distract retrieval."""
        normalized = str(query or "").strip()
        normalized = self._SCENARIO_RE.sub(" ", normalized)
        lowered = normalized.lower()
        for prefix in self._QUESTION_PREFIXES:
            if lowered.startswith(prefix):
                normalized = normalized[len(prefix) :].strip(" ?.:")
                break
        normalized = re.sub(r"\b(in|for|of)\s*$", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"\s+", " ", normalized).strip(" ?.:")
        return normalized or str(query or "").strip()

    def _tokenize(self, text: str) -> set[str]:
        return {token for token in self._TOKEN_RE.findall(str(text or "").lower()) if len(token) > 2}

    def _extract_query_anchors(self, query: str) -> set[str]:
        anchors = set()
        for raw in re.findall(r"[A-Za-z0-9_=\-/]+", str(query or "")):
            token = raw.strip(".,:;()[]{}'\"").lower()
            if len(token) >= 4 and ("-" in token or "_" in token or "=" in token or any(ch.isdigit() for ch in token)):
                anchors.add(token)
        return anchors

    def _semantic_candidates(
        self,
        query: str,
        n_results: int,
        filter_metadata: Optional[dict] = None,
    ) -> list[dict]:
        query_embedding = self.embedding_model.encode(query).tolist()
        query_params = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if filter_metadata:
            query_params["where"] = filter_metadata

        results = self.collection.query(**query_params)
        processed_results = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i]
                processed_results.append(
                    {
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "similarity": round(self._distance_to_similarity(distance), 4),
                        "distance": round(distance, 4),
                        "retrieval_strategy": "dense",
                    }
                )
        return processed_results

    def _get_keyword_corpus(self) -> list[dict]:
        if self._keyword_corpus is not None:
            return self._keyword_corpus

        corpus: list[dict] = []
        try:
            rows = self.collection.get(include=["documents", "metadatas"])
            documents = list(rows.get("documents") or [])
            metadatas = list(rows.get("metadatas") or [])
            for idx, doc in enumerate(documents):
                metadata = metadatas[idx] if idx < len(metadatas) else {}
                corpus.append(
                    {
                        "content": doc,
                        "metadata": metadata or {},
                    }
                )
        except Exception:
            corpus = []

        self._keyword_corpus = corpus
        return self._keyword_corpus

    def _keyword_candidates(
        self,
        query: str,
        top_k: int,
        filter_metadata: Optional[dict] = None,
    ) -> list[dict]:
        query_tokens = self._tokenize(query)
        query_anchors = self._extract_query_anchors(query)
        if not query_tokens and not query_anchors:
            return []

        scored = []
        for row in self._get_keyword_corpus():
            metadata = dict(row.get("metadata") or {})
            if filter_metadata and any(metadata.get(key) != value for key, value in filter_metadata.items()):
                continue

            content = str(row.get("content") or "")
            content_tokens = self._tokenize(content)
            if not content_tokens:
                continue

            token_overlap = len(query_tokens & content_tokens)
            anchor_overlap = sum(1 for anchor in query_anchors if anchor in content.lower())
            if token_overlap == 0 and anchor_overlap == 0:
                continue

            keyword_score = (token_overlap / max(1, len(query_tokens))) + (0.25 * anchor_overlap)
            scored.append(
                {
                    "content": content,
                    "metadata": metadata,
                    "similarity": 0.0,
                    "distance": 1.0,
                    "keyword_score": round(keyword_score, 4),
                    "retrieval_strategy": "keyword",
                }
            )

        scored.sort(
            key=lambda item: (
                -float(item.get("keyword_score", 0.0)),
                str((item.get("metadata") or {}).get("source", "")),
                int((item.get("metadata") or {}).get("page", -1) or -1),
            )
        )
        return scored[:top_k]

    def _candidate_key(self, row: dict) -> str:
        metadata = row.get("metadata") or {}
        return "|".join(
            [
                str(metadata.get("source", "")),
                str(metadata.get("page", "")),
                str(metadata.get("chunk_index", "")),
                str(row.get("content", ""))[:80],
            ]
        )

    def _source_boost(self, metadata: dict) -> float:
        source = str((metadata or {}).get("source", "")).lower()
        if re.search(r"data/knowledge/doc\d+\.md$", source):
            return 0.25
        if source.endswith(".md") or source.endswith(".markdown"):
            return 0.12
        if "cloud-finops-collaborative-real-time-cloud-financial-management" in source:
            return -0.08
        return 0.0

    def _rerank_candidates(self, query: str, dense_results: list[dict], keyword_results: list[dict], top_k: int) -> list[dict]:
        query_tokens = self._tokenize(query)
        query_anchors = self._extract_query_anchors(query)

        merged: dict[str, dict] = {}
        for row in dense_results + keyword_results:
            key = self._candidate_key(row)
            current = merged.get(key)
            if current is None:
                merged[key] = dict(row)
                continue

            current["similarity"] = max(float(current.get("similarity", 0.0)), float(row.get("similarity", 0.0)))
            current["distance"] = min(float(current.get("distance", 1.0)), float(row.get("distance", 1.0)))
            current["keyword_score"] = max(float(current.get("keyword_score", 0.0)), float(row.get("keyword_score", 0.0)))
            strategies = {current.get("retrieval_strategy", ""), row.get("retrieval_strategy", "")} - {""}
            current["retrieval_strategy"] = "+".join(sorted(strategies))

        reranked = []
        for row in merged.values():
            content = str(row.get("content") or "")
            metadata = dict(row.get("metadata") or {})
            content_tokens = self._tokenize(content)
            token_overlap = len(query_tokens & content_tokens) / max(1, len(query_tokens)) if query_tokens else 0.0
            anchor_overlap = sum(1 for anchor in query_anchors if anchor in content.lower())
            anchor_score = min(anchor_overlap * 0.2, 0.4)
            semantic_score = float(row.get("similarity", 0.0))
            keyword_score = max(float(row.get("keyword_score", 0.0)), token_overlap)
            hybrid_score = (
                (0.5 * semantic_score)
                + (0.35 * keyword_score)
                + (0.1 * anchor_score)
                + self._source_boost(metadata)
            )
            reranked.append(
                {
                    **row,
                    "keyword_score": round(keyword_score, 4),
                    "anchor_score": round(anchor_score, 4),
                    "hybrid_score": round(hybrid_score, 4),
                }
            )

        reranked.sort(
            key=lambda item: (
                -float(item.get("hybrid_score", 0.0)),
                -float(item.get("similarity", 0.0)),
                -float(item.get("keyword_score", 0.0)),
            )
        )

        selected = []
        per_source: dict[str, int] = {}
        for row in reranked:
            source = str((row.get("metadata") or {}).get("source", ""))
            if per_source.get(source, 0) >= self.max_per_source:
                continue
            selected.append(row)
            per_source[source] = per_source.get(source, 0) + 1
            if len(selected) >= top_k:
                return selected

        for row in reranked:
            if row in selected:
                continue
            selected.append(row)
            if len(selected) >= top_k:
                break
        return selected
    
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
        normalized_query = self._normalize_query(query)
        # Check cache first
        if self.use_cache and self._cache:
            cached = self._cache.get(
                "historical",
                query=query,
                normalized_query=normalized_query,
                top_k=top_k,
                min_similarity=min_similarity,
                filter_metadata=filter_metadata,
                hybrid_enabled=self.hybrid_enabled,
            )
            if cached is not None:
                return cached

        candidate_count = max(top_k * self.candidate_multiplier, top_k)
        dense_queries = [query]
        if normalized_query and normalized_query != query:
            dense_queries.append(normalized_query)

        dense_candidates: list[dict] = []
        seen_dense = set()
        for dense_query in dense_queries:
            for row in self._semantic_candidates(dense_query, candidate_count, filter_metadata=filter_metadata):
                key = self._candidate_key(row)
                if key in seen_dense:
                    continue
                seen_dense.add(key)
                dense_candidates.append(row)

        if self.hybrid_enabled:
            keyword_candidates = self._keyword_candidates(normalized_query or query, candidate_count, filter_metadata=filter_metadata)
            processed_results = self._rerank_candidates(normalized_query or query, dense_candidates, keyword_candidates, top_k=top_k)
        else:
            processed_results = dense_candidates[:top_k]

        processed_results = [
            row
            for row in processed_results
            if float(row.get("similarity", 0.0)) >= min_similarity or float(row.get("keyword_score", 0.0)) > 0.0
        ]
        
        # Cache results
        if self.use_cache and self._cache:
            self._cache.set(
                "historical",
                processed_results,
                query=query,
                normalized_query=normalized_query,
                top_k=top_k,
                min_similarity=min_similarity,
                filter_metadata=filter_metadata,
                hybrid_enabled=self.hybrid_enabled,
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
        self._keyword_corpus = None


# Singleton instance
_retriever_instance: Optional[RAGRetriever] = None


def get_retriever() -> RAGRetriever:
    """Get or create global retriever instance."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = RAGRetriever()
    return _retriever_instance
