"""
Peta Inovasi Router - CLEAN VERSION (No Clustering)
==================================================
Fungsi: Mengelola data poin peta dan rekomendasi kolaborasi.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List
import traceback
from datetime import datetime

from app.database import database as supabase_client
from app.services.nlp_service import nlp_service
from app.services.recommendationmap_service import recommendationmap_service

router = APIRouter(prefix="/api/peta-inovasi", tags=["Peta Inovasi"])

# ================================================================
# HELPER: Ambil data inovasi valid (punya koordinat)
# REVISI: Tambah kolom video dan link_video
# ================================================================

async def _fetch_valid_innovations() -> List[dict]:
    query = """
        SELECT no, judul_inovasi, deskripsi, lat, lon, pemda, jenis, kematangan,
               urusan_utama, urusan_lain_yang_beririsan, video, link_video
        FROM data_inovasi
        WHERE lat IS NOT NULL AND lon IS NOT NULL
    """
    rows = await supabase_client.fetch_all(query)
    return [dict(row) for row in rows]


# ================================================================
# GET /points (Peta Utama)
# ================================================================

@router.get("/points")
async def get_all_innovation_points():
    """
    Mengambil semua data titik inovasi untuk ditampilkan di peta.
    Termasuk kolom video dan link_video untuk tombol video di detail inovasi.
    """
    try:
        valid_innovations = await _fetch_valid_innovations()
        if not valid_innovations:
            raise HTTPException(status_code=404, detail="No innovation data found")

        return {
            "total": len(valid_innovations),
            "innovations": valid_innovations
        }
    except Exception as e:
        print(f"❌ ERROR PETA /points: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================================================================
# GET /statistics
# ================================================================

@router.get("/statistics")
async def get_map_statistics():
    try:
        rows = await supabase_client.fetch_all(
            "SELECT lat, lon, jenis, kematangan FROM data_inovasi"
        )
        data  = [dict(r) for r in rows]
        total = len(data)
        with_coords  = sum(1 for d in data if d.get("lat") and d.get("lon"))
        jenis_dist   = {}
        for inv in data:
            j = inv.get("jenis") or "Unknown"
            jenis_dist[j] = jenis_dist.get(j, 0) + 1
        avg_mat = sum(d.get("kematangan", 0) for d in data) / total if total else 0

        return {
            "total_innovations":    total,
            "with_coordinates":     with_coords,
            "without_coordinates":  total - with_coords,
            "jenis_distribution":   jenis_dist,
            "average_kematangan":   round(avg_mat, 2),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ================================================================
# POST /sync-cache (Logika Rekomendasi NLP)
# ================================================================

@router.post("/sync-cache")
async def sync_collaboration_cache(
    similarity_threshold: float = Query(0.45, description="Min similarity score disimpan ke cache"),
):
    try:
        valid_innovations = await _fetch_valid_innovations()
        if not valid_innovations:
            raise HTTPException(status_code=404, detail="No valid innovation data")

        descriptions = []
        for inv in valid_innovations:
            judul = inv.get("judul_inovasi") or ""
            utama = inv.get("urusan_utama") or ""
            lain  = inv.get("urusan_lain_yang_beririsan") or ""
            desc  = inv.get("deskripsi") or ""

            teks_urusan = f"Urusan {utama}."
            if lain and lain.lower() != "tidak ada":
                teks_urusan += f" Beririsan dengan {lain}."

            descriptions.append(f"{judul}. {teks_urusan} {desc}")

        embeddings = nlp_service.compute_embeddings(descriptions)
        similar_pairs = nlp_service.find_similar_innovations(embeddings, threshold=similarity_threshold)

        recs_raw = recommendationmap_service.generate_recommendations(valid_innovations, similar_pairs)
        recs_ranked = recommendationmap_service.rank_by_impact_potential(recs_raw, valid_innovations)

        # Batasi max 3 koneksi per inovasi
        kuota = {}
        final_recs = []
        for rec in recs_ranked:
            id1, id2 = rec["inovasi_1_id"], rec["inovasi_2_id"]
            if kuota.get(id1, 0) < 3 and kuota.get(id2, 0) < 3:
                final_recs.append(rec)
                kuota[id1] = kuota.get(id1, 0) + 1
                kuota[id2] = kuota.get(id2, 0) + 1

        await supabase_client.execute("DELETE FROM peta_kolaborasi_cache")

        inserted = 0
        for rec in final_recs:
            insert_sql = """
                INSERT INTO peta_kolaborasi_cache
                (inovasi_1_id, inovasi_1_judul, inovasi_2_id, inovasi_2_judul,
                 similarity_score, distance_km, is_feasible, collaboration_reason, impact_score)
                VALUES (:i1id, :i1j, :i2id, :i2j, :sim, :dist, :feas, :reas, :imp)
            """
            await supabase_client.execute(insert_sql, {
                "i1id": rec["inovasi_1_id"], "i1j": rec["inovasi_1_judul"],
                "i2id": rec["inovasi_2_id"], "i2j": rec["inovasi_2_judul"],
                "sim": float(rec["similarity_score"]), "dist": float(rec["distance_km"]),
                "feas": bool(rec["is_feasible"]), "reas": rec.get("collaboration_reason", ""),
                "imp": float(rec.get("impact_score", 0))
            })
            inserted += 1

        return {
            "status": "success",
            "pairs_found": len(similar_pairs),
            "recs_inserted": inserted,
            "generated_at": datetime.utcnow().isoformat()
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Server error: {e}")


# ================================================================
# GET /recommendations/{inovasi_id} (Filter Jarak 50 KM)
# ================================================================

@router.get("/recommendations/{inovasi_id}")
async def get_recommendations_for_innovation(
    inovasi_id: int,
    top_n: int             = Query(5,    description="Jumlah maksimal rekomendasi"),
    max_distance_km: float = Query(50.0, description="Batas jarak maksimal (km) — 50 km"),
):
    try:
        query = """
            SELECT * FROM peta_kolaborasi_cache
            WHERE (inovasi_1_id = :target_id OR inovasi_2_id = :target_id)
            AND distance_km <= :max_dist
            ORDER BY impact_score DESC, similarity_score DESC
            LIMIT :limit
        """
        rows = await supabase_client.fetch_all(query, {
            "target_id": inovasi_id,
            "max_dist":  max_distance_km,
            "limit":     top_n
        })

        return {
            "inovasi_id": inovasi_id,
            "total": len(rows),
            "recommendations": [dict(r) for r in rows]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))