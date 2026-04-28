from fastapi import APIRouter, Query, BackgroundTasks
from app.services.clustering_service import run_clustering_pipeline, get_cluster_cache
from app.services.recommendation_service import (
    recommend_for_inovasi,
    get_top_collaboration_recommendations,
)

router = APIRouter(tags=["Recommendations"])


# ===============================
# JALANKAN CLUSTERING (BACKGROUND)
# ===============================
@router.post("/run")
async def run_pipeline(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_clustering_pipeline)
    return {
        "status": "processing",
        "message": "Clustering sedang berjalan di background",
    }


# ===============================
# TOP REKOMENDASI KOLABORASI (DARI CLUSTERING CACHE)
# Selalu kembalikan top 3 dari cache (diurutkan skor tertinggi),
# berapapun jumlah cluster yang dihasilkan.
# ===============================
@router.get("/top-clusters")
async def top_cluster_collaborations(limit: int = Query(3, ge=1, le=20)):
    insights, last_run = get_cluster_cache()

    if not insights:
        return {
            "status": "empty",
            "message": "Clustering belum dijalankan atau masih diproses",
            "data": [],
        }

    # Selalu ambil top-N berdasarkan skor_kolaborasi tertinggi,
    # tidak terbatas 1 per cluster
    top = insights[:limit]

    return {
        "status": "ok",
        "total_clusters": len(insights),
        "showing": len(top),
        "last_run": last_run.isoformat() if last_run else None,
        "data": top,
    }


# ===============================
# TOP REKOMENDASI KOLABORASI (DARI DATABASE)
# Query langsung ke similarity_result — top 3 global,
# bukan per cluster, sehingga selalu ada data meskipun
# k cluster kecil.
# ===============================
@router.get("/top")
async def top_collaboration_db(
    limit: int = Query(3, ge=1, le=20),
    min_similarity: float = Query(0.3, ge=0, le=1),
):
    data = await get_top_collaboration_recommendations(
        limit=limit, min_similarity=min_similarity
    )

    return {
        "status": "ok",
        "total": len(data),
        "data": data,
    }
