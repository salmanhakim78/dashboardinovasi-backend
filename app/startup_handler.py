"""
Startup Handler for FastAPI Application - OOM FIXED VERSION
Handles initialization of vector search cache and clustering cache
✅ FIXED: Removed heavy cache loading at startup to prevent Out of Memory
✅ Cache will load lazily on first request instead
"""

from fastapi import FastAPI
from app.database import database
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler untuk FastAPI.
    Menjalankan inisialisasi saat aplikasi start dan cleanup saat shutdown.
    """
    # =====================================
    # STARTUP EVENTS
    # =====================================
    print("\n" + "=" * 60)
    print("🚀 BRIDA AI System Starting...")
    print("=" * 60)

    # STEP 0: CONNECT TO DATABASE ONLY
    # ✅ Tidak load cache saat startup untuk mencegah OOM
    # Cache akan di-load secara lazy saat pertama kali dibutuhkan
    print("\n📊 Connecting to Database...")
    try:
        await database.connect()
        print("✅ Database connected successfully")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("⚠️ Application will run with limited functionality")

    print("\n" + "=" * 60)
    print("✅ BRIDA AI System Ready!")
    print("=" * 60 + "\n")

    # Yield control to the application
    yield

    # =====================================
    # SHUTDOWN EVENTS
    # =====================================
    print("\n" + "=" * 60)
    print("👋 BRIDA AI System Shutting Down...")
    print("=" * 60)

    # DISCONNECT DATABASE
    try:
        await database.disconnect()
        print("✅ Database disconnected")
    except Exception as e:
        print(f"⚠️ Database disconnect error: {e}")

    print("=" * 60 + "\n")


# =====================================
# MANUAL REFRESH ENDPOINTS (Optional)
# =====================================
from fastapi import APIRouter, BackgroundTasks

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.post("/refresh-vector-cache")
async def refresh_vector_cache(background_tasks: BackgroundTasks):
    """
    Manually refresh vector search cache.
    Use this after importing new data.
    """
    from app.services.vector_search_service import refresh_embeddings_cache

    background_tasks.add_task(refresh_embeddings_cache)

    return {
        "status": "processing",
        "message": "Vector search cache refresh started in background",
    }


@router.post("/refresh-clustering-cache")
async def refresh_clustering_cache(background_tasks: BackgroundTasks):
    """
    Manually refresh clustering cache from database.
    Use this after running clustering manually.
    """
    from app.services.clustering_service import load_cache_from_database

    background_tasks.add_task(load_cache_from_database)

    return {
        "status": "processing",
        "message": "Clustering cache refresh started in background",
    }


@router.post("/refresh-all-caches")
async def refresh_all_caches(background_tasks: BackgroundTasks):
    """
    Refresh all caches (vector + clustering).
    Use this after major data updates.
    """
    from app.services.vector_search_service import refresh_embeddings_cache
    from app.services.clustering_service import load_cache_from_database

    async def refresh_all():
        await refresh_embeddings_cache()
        await load_cache_from_database()

    background_tasks.add_task(refresh_all)

    return {
        "status": "processing",
        "message": "All caches refresh started in background",
    }


@router.get("/cache-status")
async def get_cache_status():
    """
    Check status of all caches.
    """
    from app.services.vector_search_service import (
        _cache_loaded as vector_loaded,
        _inovasi_data_cache,
    )
    from app.services.clustering_service import get_cluster_cache

    cluster_data, cluster_last_run = get_cluster_cache()

    return {
        "database": {
            "connected": database.is_connected,
        },
        "vector_cache": {
            "loaded": vector_loaded,
            "total_items": len(_inovasi_data_cache) if _inovasi_data_cache else 0,
        },
        "clustering_cache": {
            "total_clusters": len(cluster_data) if cluster_data else 0,
            "last_run": (cluster_last_run.isoformat() if cluster_last_run else None),
        },
    }