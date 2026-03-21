"""RAG Memory module — long-term memory for the SOC investigation agent.

Uses ChromaDB (embedded, no server needed) to store and retrieve
InvestigationReport objects as semantic embeddings.

How it works:
  1. After each investigation, store_report() embeds the report summary
     into ChromaDB with full metadata as payload.
  2. Before each new investigation, search_similar_incidents() finds
     historically similar reports using cosine similarity on embeddings.
  3. The agent receives this context and can reference past confirmed threats.

Benefits:
  - Catches repeat offenders automatically
  - Detects coordinated campaigns (multiple insiders with same pattern)
  - Improves confidence calibration over time
  - Zero external dependencies — runs fully locally
"""

import json
import os
from pathlib import Path
from typing import Optional

# Memory storage path (alongside the SQLite DB)
MEMORY_DIR = Path(__file__).resolve().parents[2] / "data" / "processed" / "agent_memory"
COLLECTION_NAME = "investigation_reports"

# Embedding model (local, no API key needed)
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # 22MB, fast, good quality

_client = None
_collection = None


def _get_collection():
    """Lazy-initialize ChromaDB client and collection."""
    global _client, _collection

    if _collection is not None:
        return _collection

    try:
        import chromadb
        from chromadb.utils import embedding_functions

        MEMORY_DIR.mkdir(parents=True, exist_ok=True)

        _client = chromadb.PersistentClient(path=str(MEMORY_DIR))

        # Use sentence-transformers for local embeddings (no API key)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )

        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
        return _collection

    except ImportError as e:
        raise ImportError(
            f"RAG memory requires: pip install chromadb sentence-transformers\n"
            f"Missing: {e}"
        )


def store_report(report: dict) -> bool:
    """Store an InvestigationReport in the vector database.

    Args:
        report: The dict returned by react_agent.investigate()
                Must contain at least 'user_id', 'summary', 'threat_scenario'.

    Returns:
        True if stored successfully, False otherwise.
    """
    try:
        collection = _get_collection()

        user_id = report.get("user_id", "unknown")
        summary = report.get("summary", "")
        threat = report.get("threat_scenario", "UNKNOWN")
        confidence = report.get("confidence", 0.0)
        severity = report.get("severity", "UNKNOWN")
        risk_score = report.get("risk_score", 0.0)
        reasoning = report.get("reasoning", "")
        evidence = report.get("evidence_chain", [])

        # The text we embed — rich enough for semantic search
        document_text = (
            f"Threat: {threat}. Severity: {severity}. "
            f"Summary: {summary} "
            f"Reasoning: {reasoning[:500]} "
            f"Evidence: {' | '.join(evidence[:5])}"
        )

        # Unique document ID (user + timestamp)
        import time
        doc_id = f"{user_id}_{int(time.time())}"

        # Metadata stored alongside the embedding
        metadata = {
            "user_id": user_id,
            "threat_scenario": threat,
            "severity": severity,
            "confidence": float(confidence),
            "risk_score": float(risk_score),
            "summary": summary[:500],
            "recommended_action": report.get("recommended_action", "UNKNOWN"),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        collection.add(
            documents=[document_text],
            metadatas=[metadata],
            ids=[doc_id],
        )

        print(f"  [MEMORY] ✅ Stored report for {user_id} (id={doc_id})")
        return True

    except Exception as e:
        print(f"  [MEMORY] ⚠️  Failed to store report: {e}")
        return False


def search_similar_incidents(query: str, top_n: int = 3) -> list[dict]:
    """Search past investigation reports for semantically similar patterns.

    Args:
        query: Natural language description of what to search for.
               e.g. "after-hours USB file copies combined with wikileaks browsing"
        top_n: Number of results to return.

    Returns:
        List of metadata dicts for the most similar past incidents.
        Empty list if no results or memory is empty.
    """
    try:
        collection = _get_collection()

        if collection.count() == 0:
            return []

        results = collection.query(
            query_texts=[query],
            n_results=min(top_n, collection.count()),
        )

        if not results or not results["metadatas"]:
            return []

        # results["metadatas"] is a list of lists (one per query)
        return results["metadatas"][0]

    except Exception as e:
        print(f"  [MEMORY] Search failed: {e}")
        return []


def get_memory_stats() -> dict:
    """Return statistics about the memory store."""
    try:
        collection = _get_collection()
        count = collection.count()
        return {"total_reports": count, "memory_dir": str(MEMORY_DIR), "status": "ok"}
    except Exception as e:
        return {"total_reports": 0, "status": f"error: {e}"}
