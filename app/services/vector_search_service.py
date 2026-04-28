"""
Vector Search Service for Chatbot Enhancement
Handles semantic search using embeddings to find relevant innovations
even when there are typos or semantic variations.
✅ FIXED: Lazy loading model to prevent Out of Memory on startup
"""

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from app.database import database
from typing import List, Dict, Optional
import asyncio

# ===============================
# MODEL - LAZY LOADED
# ✅ Tidak di-load saat import, tapi saat pertama kali dibutuhkan
# ===============================
_embedding_model = None


def get_embedding_model():
    """Lazy load model hanya saat pertama kali dibutuhkan"""
    global _embedding_model
    if _embedding_model is None:
        print("🔄 Loading embedding model (first time)...")
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        print("✅ Embedding model loaded")
    return _embedding_model


# ===============================
# CACHE FOR EMBEDDINGS
# ===============================
_embeddings_cache: Optional[np.ndarray] = None
_inovasi_data_cache: Optional[List[Dict]] = None
_cache_loaded: bool = False


# ===============================
# LOAD & CACHE ALL INOVASI EMBEDDINGS
# ===============================
async def load_inovasi_embeddings_cache():
    """
    Load semua data inovasi dan embeddings ke memory.
    Call ini saat startup aplikasi atau periodic refresh.
    """
    global _embeddings_cache, _inovasi_data_cache, _cache_loaded

    try:
        print("🔄 Loading inovasi embeddings cache...")

        # Fetch all inovasi data
        rows = await database.fetch_all(
            """
            SELECT
                id,
                judul_inovasi,
                admin_opd,
                urusan_utama,
                tahapan_inovasi,
                label_kematangan,
                bentuk_inovasi,
                jenis
            FROM data_inovasi
            WHERE judul_inovasi IS NOT NULL
            ORDER BY id
            """
        )

        if not rows:
            print("⚠️ No inovasi data found")
            return False

        # Convert to list of dicts
        _inovasi_data_cache = [dict(r) for r in rows]

        # Build embeddings
        texts = []
        for item in _inovasi_data_cache:
            text = (
                f"Judul: {item['judul_inovasi']}. "
                f"Urusan: {item.get('urusan_utama', '')}. "
                f"Tahapan: {item.get('tahapan_inovasi', '')}. "
                f"Kematangan: {item.get('label_kematangan', '')}"
            )
            texts.append(text)

        # Generate embeddings (lazy load model here)
        model = get_embedding_model()
        _embeddings_cache = model.encode(texts, show_progress_bar=False)

        _cache_loaded = True
        print(f"✅ Embeddings cache loaded: {len(_inovasi_data_cache)} items")
        return True

    except Exception as e:
        print(f"❌ Error loading embeddings cache: {e}")
        import traceback
        traceback.print_exc()
        return False


# ===============================
# REFRESH CACHE
# ===============================
async def refresh_embeddings_cache():
    """
    Refresh cache embeddings.
    Call ini setelah ada data baru ditambahkan.
    """
    global _cache_loaded
    _cache_loaded = False
    return await load_inovasi_embeddings_cache()


# ===============================
# VECTOR SEARCH
# ===============================
async def vector_search_inovasi(
    query: str, top_k: int = 5, min_similarity: float = 0.3
) -> List[Dict]:
    """
    Cari inovasi menggunakan semantic similarity.
    """
    global _embeddings_cache, _inovasi_data_cache, _cache_loaded

    # Auto-load cache if not loaded
    if not _cache_loaded:
        success = await load_inovasi_embeddings_cache()
        if not success:
            return []

    if _embeddings_cache is None or _inovasi_data_cache is None:
        return []

    try:
        # Generate query embedding (lazy load model)
        model = get_embedding_model()
        query_embedding = model.encode([query], show_progress_bar=False)

        # Calculate cosine similarity
        similarities = cosine_similarity(query_embedding, _embeddings_cache)[0]

        # Get top-k results
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score < min_similarity:
                continue
            inovasi = _inovasi_data_cache[idx].copy()
            inovasi["similarity_score"] = round(score, 4)
            results.append(inovasi)

        print(f"🔍 Vector search for '{query}': found {len(results)} results")
        if results:
            print(
                f"   Top result: {results[0]['judul_inovasi']} (score: {results[0]['similarity_score']})"
            )

        return results

    except Exception as e:
        print(f"❌ Vector search error: {e}")
        import traceback
        traceback.print_exc()
        return []


# ===============================
# HYBRID SEARCH (Vector + SQL LIKE)
# ===============================
async def hybrid_search_inovasi(
    query: str, keywords: List[str], top_k: int = 3
) -> Optional[Dict]:
    """
    Gabungkan vector search + SQL LIKE search.
    """
    print(f"\n{'='*60}")
    print(f"HYBRID SEARCH: '{query}'")
    print(f"Keywords: {keywords}")
    print(f"{'='*60}")

    sql_results = []
    vector_results = []

    # 1. SQL LIKE Search
    if keywords:
        for keyword in keywords:
            query_sql = """
            SELECT 
                id, 
                judul_inovasi, 
                admin_opd, 
                bentuk_inovasi, 
                jenis,
                urusan_utama,
                tahapan_inovasi,
                label_kematangan
            FROM data_inovasi
            WHERE judul_inovasi ILIKE :keyword 
               OR admin_opd ILIKE :keyword
               OR urusan_utama ILIKE :keyword
            ORDER BY 
                CASE 
                    WHEN judul_inovasi ILIKE :keyword THEN 1
                    WHEN admin_opd ILIKE :keyword THEN 2
                    ELSE 3
                END
            LIMIT 3
            """
            results = await database.fetch_all(query_sql, {"keyword": f"%{keyword}%"})
            if results:
                sql_results.extend([dict(r) for r in results])
                print(f"✅ SQL found {len(results)} results for keyword: '{keyword}'")

    # 2. Vector Search
    vector_results = await vector_search_inovasi(
        query, top_k=top_k, min_similarity=0.25
    )

    # 3. Combine & Rank Results
    combined = {}

    for item in sql_results:
        item_id = item["id"]
        if item_id not in combined:
            combined[item_id] = {
                **item,
                "match_score": 1.0,
                "match_type": "exact",
            }

    for item in vector_results:
        item_id = item["id"]
        if item_id not in combined:
            combined[item_id] = {
                **item,
                "match_score": item["similarity_score"],
                "match_type": "semantic",
            }
        else:
            combined[item_id]["match_score"] = max(
                combined[item_id]["match_score"],
                item["similarity_score"] * 0.8,
            )
            combined[item_id]["match_type"] = "hybrid"

    ranked_results = sorted(
        combined.values(), key=lambda x: x["match_score"], reverse=True
    )

    if ranked_results:
        best_match = ranked_results[0]
        print(f"\n✅ BEST MATCH:")
        print(f"   Judul: {best_match['judul_inovasi']}")
        print(f"   OPD: {best_match.get('admin_opd', '-')}")
        print(f"   Score: {best_match['match_score']:.4f} ({best_match['match_type']})")
        return best_match
    else:
        print(f"❌ No matches found")
        return None


# ===============================
# VECTOR SEARCH FOR COLLABORATION
# ===============================
async def vector_search_collaboration(
    inovasi_id: int, top_k: int = 5, min_similarity: float = 0.3
) -> List[Dict]:
    """
    Cari inovasi yang mirip untuk kolaborasi menggunakan vector similarity.
    """
    global _embeddings_cache, _inovasi_data_cache, _cache_loaded

    if not _cache_loaded:
        await load_inovasi_embeddings_cache()

    if _embeddings_cache is None or _inovasi_data_cache is None:
        return []

    try:
        # Find index of target inovasi
        target_idx = None
        for idx, item in enumerate(_inovasi_data_cache):
            if item["id"] == inovasi_id:
                target_idx = idx
                break

        if target_idx is None:
            print(f"❌ Inovasi ID {inovasi_id} not found in cache")
            return []

        # Get embedding of target inovasi
        target_embedding = _embeddings_cache[target_idx].reshape(1, -1)

        # Calculate similarity with all other inovasi
        similarities = cosine_similarity(target_embedding, _embeddings_cache)[0]

        # Get top-k results (excluding self)
        top_indices = np.argsort(similarities)[::-1]

        results = []
        for idx in top_indices:
            if idx == target_idx:
                continue
            score = float(similarities[idx])
            if score < min_similarity:
                continue
            inovasi = _inovasi_data_cache[idx].copy()
            inovasi["similarity_score"] = round(score, 4)
            results.append(inovasi)
            if len(results) >= top_k:
                break

        print(
            f"🔍 Collaboration search for inovasi {inovasi_id}: found {len(results)} similar items"
        )
        return results

    except Exception as e:
        print(f"❌ Collaboration vector search error: {e}")
        import traceback
        traceback.print_exc()
        return []