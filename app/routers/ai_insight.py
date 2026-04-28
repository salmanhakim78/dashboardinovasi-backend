from fastapi import APIRouter, Query
from datetime import date
from app.database import database
from app.services.ai_service import call_gemini
from app.services.insight_builder import (
    build_insight_prompt,
    build_collaboration_prompt,
)
from pydantic import BaseModel
import json

router = APIRouter(prefix="/dashboard", tags=["AI Insight"])


class UrusanBreakdown(BaseModel):
    inisiatif: int
    ujiCoba: int
    penerapan: int


class Top5UrusanItem(BaseModel):
    nama: str
    total: int
    breakdown: UrusanBreakdown


class JenisInovasiItem(BaseModel):
    jenis: str
    jumlah: int
    persentase: str


class WatchlistItemSummary(BaseModel):
    nama: str
    skor: int


class WatchlistSummary(BaseModel):
    count: int
    items: list[WatchlistItemSummary]


class AnalyticsSummary(BaseModel):
    totalInovasi: int
    digitalCount: int
    digitalPercent: float
    topUrusan: str
    watchlistCount: int
    avgKematangan: float
    tahun: str


class AIInsightRequest(BaseModel):
    summary: AnalyticsSummary
    top5Urusan: list[Top5UrusanItem]
    jenisInovasi: list[JenisInovasiItem]
    watchlist: WatchlistSummary


# ===============================
# AI INSIGHT DASHBOARD
# ===============================
@router.get("/ai-insight")
async def get_ai_insight(force_refresh: bool = False):
    today = date.today()
    cache_key = str(today)

    print(
        f"🔍 Fetching AI Insight for dashboard with cache_key: {cache_key}, force_refresh: {force_refresh}"
    )

    try:
        if not force_refresh:
            cache = await database.fetch_one(
                """
                SELECT insight_data
                FROM ai_insight_cache
                WHERE insight_type = 'dashboard'
                  AND cache_key = :key
                """,
                {"key": cache_key},
            )

            if cache and cache["insight_data"]:
                print(f"✅ Cache HIT for dashboard - returning cached data")
                insight_data = cache["insight_data"]
                if isinstance(insight_data, str):
                    return json.loads(insight_data)
                return insight_data

        print(
            f"🔄 {'Force refresh' if force_refresh else 'Cache MISS'} - generating new insights"
        )

        stats = await database.fetch_one(
            """
            SELECT
                COUNT(*) AS total_inovasi,
                COUNT(*) FILTER (WHERE jenis = 'Digital') AS inovasi_digital,
                COUNT(*) FILTER (
                    WHERE EXTRACT(YEAR FROM tanggal_penerapan) = EXTRACT(YEAR FROM CURRENT_DATE)
                ) AS inovasi_tahun_ini,
                ROUND(AVG(kematangan)::numeric, 1) AS rata_kematangan
            FROM data_inovasi;
            """
        )

        trend = await database.fetch_all(
            """
            SELECT
                EXTRACT(YEAR FROM tanggal_penerapan)::int AS tahun,
                jenis,
                COUNT(*) AS jumlah
            FROM data_inovasi
            WHERE tanggal_penerapan IS NOT NULL
                AND EXTRACT(YEAR FROM tanggal_penerapan) >= 2022
            GROUP BY tahun, jenis
            ORDER BY tahun, jenis;
            """
        )

        top_opd = await database.fetch_all(
            """
            SELECT admin_opd, COUNT(*) AS jumlah
            FROM data_inovasi
            GROUP BY admin_opd
            ORDER BY jumlah DESC
            LIMIT 5;
            """
        )

        tahap_dist = await database.fetch_all(
            """
            SELECT tahapan_inovasi, COUNT(*) AS jumlah
            FROM data_inovasi
            GROUP BY tahapan_inovasi
            ORDER BY jumlah DESC;
            """
        )

        top_urusan = await database.fetch_all(
            """
            SELECT urusan_utama, COUNT(*) AS jumlah
            FROM data_inovasi
            GROUP BY urusan_utama
            ORDER BY jumlah DESC
            LIMIT 5;
            """
        )

        print(f"📊 Data fetched - Stats: {stats}")
        print(f"📊 Trend records: {len(trend)}")
        print(f"📊 Top OPD records: {len(top_opd)}")

        prompt = build_insight_prompt(stats, trend, top_opd, tahap_dist, top_urusan)

        try:
            print(f"Calling Gemini API for dashboard insights...")
            ai_text = call_gemini(prompt, mode="insight")

            ai_text_clean = ai_text.strip()
            if ai_text_clean.startswith("```"):
                ai_text_clean = ai_text_clean.replace("```json", "").replace("```", "")

            insights = json.loads(ai_text_clean)

            if not isinstance(insights, list):
                raise ValueError("Invalid insights structure")

            valid_insights = [
                i
                for i in insights
                if isinstance(i, dict) and "icon" in i and "text" in i and "type" in i
            ]

            if len(valid_insights) < 3:
                print(
                    f"⚠️ Not enough valid insights ({len(valid_insights)}), using fallback"
                )
                insights = generate_dashboard_fallback(stats, top_opd, top_urusan)
            else:
                insights = valid_insights

            print(f"✅ Generated {len(insights)} insights successfully")

            await database.execute(
                """
                INSERT INTO ai_insight_cache (insight_type, cache_key, insight_data)
                VALUES ('dashboard', :key, :data)
                ON CONFLICT (insight_type, cache_key)
                DO UPDATE SET insight_data = EXCLUDED.insight_data, created_at = CURRENT_TIMESTAMP
                """,
                {"key": cache_key, "data": json.dumps(insights)},
            )

            return insights

        except json.JSONDecodeError as e:
            print(f"❌ JSON Decode Error: {e}")
            insights = generate_dashboard_fallback(stats, top_opd, top_urusan)
            await database.execute(
                """
                INSERT INTO ai_insight_cache (insight_type, cache_key, insight_data)
                VALUES ('dashboard', :key, :data)
                ON CONFLICT (insight_type, cache_key)
                DO UPDATE SET insight_data = EXCLUDED.insight_data, created_at = CURRENT_TIMESTAMP
                """,
                {"key": cache_key, "data": json.dumps(insights)},
            )
            return insights

        except Exception as e:
            print(f"❌ AI Generation Error: {e}")
            insights = generate_dashboard_fallback(stats, top_opd, top_urusan)
            await database.execute(
                """
                INSERT INTO ai_insight_cache (insight_type, cache_key, insight_data)
                VALUES ('dashboard', :key, :data)
                ON CONFLICT (insight_type, cache_key)
                DO UPDATE SET insight_data = EXCLUDED.insight_data, created_at = CURRENT_TIMESTAMP
                """,
                {"key": cache_key, "data": json.dumps(insights)},
            )
            return insights

    except Exception as e:
        print(f"❌ Dashboard Insight Error: {e}")
        return [
            {
                "icon": "📊",
                "text": "Sistem sedang mengalami gangguan dalam menghasilkan insight. Silakan coba lagi nanti.",
                "type": "info",
            }
        ]


def generate_dashboard_fallback(stats, top_opd, top_urusan):
    total = stats["total_inovasi"] or 0
    digital = stats["inovasi_digital"] or 0
    tahun_ini = stats["inovasi_tahun_ini"] or 0
    rata_kematangan = float(stats["rata_kematangan"] or 0)
    digital_pct = (digital / total * 100) if total > 0 else 0
    top_opd_name = top_opd[0]["admin_opd"] if top_opd else "N/A"
    top_opd_count = top_opd[0]["jumlah"] if top_opd else 0
    top_urusan_name = top_urusan[0]["urusan_utama"] if top_urusan else "N/A"
    top_urusan_count = top_urusan[0]["jumlah"] if top_urusan else 0

    return [
        {
            "icon": "📊",
            "type": "info",
            "text": f"Saat ini tercatat {total} inovasi daerah dengan tingkat digitalisasi mencapai {digital_pct:.1f}% ({digital} dari {total} inovasi bersifat digital).",
        },
        {
            "icon": "🏆",
            "type": "success",
            "text": f"{top_opd_name} memimpin dengan {top_opd_count} inovasi, menunjukkan komitmen kuat dalam pengembangan layanan publik.",
        },
        {
            "icon": "🎯",
            "type": "success",
            "text": f"{top_urusan_name} menjadi fokus utama dengan {top_urusan_count} inovasi, mencerminkan prioritas strategis pemerintah daerah.",
        },
        {
            "icon": "📈",
            "type": "info",
            "text": f"Tahun ini telah diluncurkan {tahun_ini} inovasi baru dengan skor kematangan rata-rata {rata_kematangan:.1f}.",
        },
        {
            "icon": "💡",
            "type": "warning" if rata_kematangan < 60 else "success",
            "text": f"Skor kematangan rata-rata {rata_kematangan:.1f} menunjukkan {'perlu peningkatan dalam implementasi dan keberlanjutan inovasi' if rata_kematangan < 60 else 'kualitas implementasi inovasi yang baik'}.",
        },
    ]


# ===============================
# AI ANALISIS TOP REKOMENDASI KOLABORASI
# ===============================
@router.get("/ai-collaboration")
async def ai_collaboration_insight(inovasi_1: int, inovasi_2: int):
    query = """
    SELECT
        s.similarity,
        a.judul_inovasi  AS inovasi_1,
        b.judul_inovasi  AS inovasi_2,
        a.admin_opd      AS opd_1,
        b.admin_opd      AS opd_2,
        a.urusan_utama   AS urusan,
        b.urusan_utama   AS urusan_2,
        a.tahapan_inovasi AS tahap,
        b.tahapan_inovasi AS tahap_2,
        a.deskripsi      AS deskripsi_1,
        b.deskripsi      AS deskripsi_2
    FROM similarity_result s
    JOIN data_inovasi a ON a.id = s.inovasi_id_1
    JOIN data_inovasi b ON b.id = s.inovasi_id_2
    WHERE s.inovasi_id_1 = :i1
      AND s.inovasi_id_2 = :i2
    """

    data = await database.fetch_one(query, {"i1": inovasi_1, "i2": inovasi_2})

    if not data:
        return {"status": "empty", "message": "Data kolaborasi tidak ditemukan"}

    prompt = build_collaboration_prompt(
        {
            "inovasi_1": data["inovasi_1"],
            "opd_1": data["opd_1"],
            "inovasi_2": data["inovasi_2"],
            "opd_2": data["opd_2"],
            "urusan": data["urusan"],
            "urusan_2": data["urusan_2"],
            "tahap": data["tahap"],
            "tahap_2": data["tahap_2"],
            "similarity": data["similarity"],
            "deskripsi_1": data["deskripsi_1"] or "",
            "deskripsi_2": data["deskripsi_2"] or "",
        }
    )

    try:
        ai_text = call_gemini(prompt, mode="recommendation")
        ai_text = ai_text.strip().replace("```json", "").replace("```", "")
        return json.loads(ai_text)

    except Exception as e:
        print("AI Collaboration Error:", e)
        return {"status": "error", "message": "Gagal menghasilkan analisis kolaborasi"}
