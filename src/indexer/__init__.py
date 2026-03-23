import os
import chromadb
from chromadb.config import Settings
import pandas as pd
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

_client = None
_collections = {}


def get_chroma_client():
    global _client
    if _client is None:
        chroma_dir = os.path.expanduser("~/.cli-agent/chroma")
        os.makedirs(chroma_dir, exist_ok=True)
        _client = chromadb.PersistentClient(path=chroma_dir)
    return _client


def build_index(file_path: str, text_columns: list[str] | None = None) -> dict:
    """
    Build a semantic search index from a CSV file.
    Uses sentence-transformers for embeddings.
    """
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    path = Path(normalized_path)
    
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    
    try:
        df = pd.read_csv(normalized_path)
    except Exception as e:
        return {"error": f"Failed to read CSV: {str(e)}"}
    
    if text_columns is None:
        text_columns = [col for col in df.columns if df[col].dtype == 'object']
        text_columns = text_columns[:3]
    
    if not text_columns:
        return {"error": "No text columns found for indexing. Please specify text_columns."}
    
    collection_name = f"csv_{path.stem}_{hash(normalized_path) % 10000}"
    
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
    except Exception as e:
        return {"error": f"Failed to load embedding model: {str(e)}"}
    
    try:
        client = get_chroma_client()
        
        try:
            client.delete_collection(name=collection_name)
        except:
            pass
        
        collection = client.create_collection(
            name=collection_name,
            metadata={"file_path": normalized_path}
        )
        
        texts = []
        ids = []
        metadatas = []
        
        for idx, row in df.iterrows():
            text_parts = []
            for col in text_columns:
                value = row.get(col)
                if value is not None and not (isinstance(value, float) and pd.isna(value)):
                    text_parts.append(f"{col}: {value}")
            
            if text_parts:
                combined_text = " | ".join(text_parts)
                texts.append(combined_text)
                ids.append(str(idx))
                metadatas.append({col: str(row.get(col)) for col in df.columns if row.get(col) is not None and not pd.isna(row.get(col))})
        
        if not texts:
            return {"error": "No text data to index"}
        
        embeddings = model.encode(texts, show_progress_bar=True).tolist()
        
        collection.add(
            ids=ids,
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas
        )
        
        _collections[normalized_path] = collection_name
        
        return {
            "success": True,
            "collection_name": collection_name,
            "documents_indexed": len(texts),
            "columns_used": text_columns,
        }
        
    except Exception as e:
        return {"error": f"Index building failed: {str(e)}"}


def search_index(file_path: str, query: str, n: int = 5) -> dict:
    """
    Search the index for similar documents using natural language.
    """
    normalized_path = os.path.abspath(os.path.realpath(file_path))
    
    collection_name = _collections.get(normalized_path)
    if collection_name is None:
        for stored_path, coll in _collections.items():
            if os.path.basename(stored_path) == os.path.basename(normalized_path):
                collection_name = coll
                normalized_path = stored_path
                break
    
    if collection_name is None:
        return {"error": f"No index found for {file_path}. Use /index command to build one first."}
    
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        query_embedding = model.encode([query]).tolist()
        
        client = get_chroma_client()
        collection = client.get_collection(name=collection_name)
        
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=min(n, 20)
        )
        
        if not results['documents'] or not results['documents'][0]:
            return {"error": "No matching documents found"}
        
        matches = []
        for i, doc in enumerate(results['documents'][0]):
            matches.append({
                "text": doc,
                "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                "distance": results['distances'][0][i] if results['distances'] else 0,
            })
        
        return {
            "success": True,
            "query": query,
            "matches": matches,
            "count": len(matches),
        }
        
    except Exception as e:
        return {"error": f"Search failed: {str(e)}"}


def list_indexes() -> dict:
    """List all available indexes."""
    if not _collections:
        return {"indexes": [], "message": "No indexes built yet. Use /index to build one."}
    
    indexes = []
    for path, collection in _collections.items():
        indexes.append({
            "file_path": path,
            "collection": collection,
        })
    return {"indexes": indexes}
