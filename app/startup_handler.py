"""
Startup Handler for FastAPI Application - FIXED VERSION
Handles initialization of vector search cache and clustering cache
✅ FIXED: Added database connection in lifespan context
"""

from fastapi import FastAPI
from app.database import database
from app.services.vector_search_service import load_inovasi_embeddings_cache
from app.services.clustering_service import (
    load_cache_from_database,
    check_and_auto_run_clustering,
)
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

    # ✅ STEP 0: CONNECT TO DATABASE (THIS WAS MISSING!)
    print("\n📊 Step 0: Connecting to Database...")
    try:
        await database.connect()
        print("✅ Database connected successfully")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("⚠️ Application will run with limited functionality")
        # Don't yield yet - continue with startup to allow health checks
        # but skip cache loading

    # Only continue with cache loading if database is connected
    if database.is_connected:
        # 1. Load Vector Search Embeddings Cache
        print("\n📊 Step 1: Loading Vector Search Cache...")
        embeddings_loaded = await load_inovasi_embeddings_cache()

        if embeddings_loaded:
            print("✅ Vector search cache loaded successfully")
        else:
            print("⚠️ Vector search cache loading failed (will retry on first query)")

        # 2. Load Clustering Results Cache
        print("\n📊 Step 2: Loading Clustering Cache...")
        await load_cache_from_database()
        print("✅ Clustering cache loaded")

        # 3. Auto-check for new data and trigger clustering if needed
        print("\n📊 Step 3: Checking for new data...")
        need_clustering = await check_and_auto_run_clustering(threshold=50)

        if need_clustering:
            print("✅ Auto-clustering completed")
            # Reload caches after clustering
            print("\n🔄 Reloading caches after clustering...")
            await load_inovasi_embeddings_cache()
            await load_cache_from_database()
        else:
            print("✅ No clustering needed")
    else:
        print("\n⚠️ Skipping cache initialization due to database connection failure")

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

    # ✅ DISCONNECT DATABASE
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
