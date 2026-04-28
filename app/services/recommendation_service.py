from app.database import database


# ===============================
# LABEL MAKNA SIMILARITY
# ===============================
def similarity_label(score: float):
    if score > 0.9:
        return "Potensi Replikasi Langsung"
    elif score > 0.8:
        return "Potensi Kolaborasi Pengembangan"
    else:
        return "Referensi Praktik Baik"


# ===============================
# GENERATE ALASAN OTOMATIS
# ===============================
def build_reason(row):
    alasan_parts = []

    if row["urusan_1"] == row["urusan_2"]:
        alasan_parts.append(f"berada pada urusan {row['urusan_1']}")

    if row["tahap_1"] == row["tahap_2"]:
        alasan_parts.append(f"pada tahap inovasi {row['tahap_1']}")

    if not alasan_parts:
        return "Memiliki kemiripan konteks dan pendekatan inovasi"

    return "Keduanya " + " dan ".join(alasan_parts)


# ===============================
# TOP-N REKOMENDASI KOLABORASI
# Selalu ambil top-N dari seluruh similarity_result,
# tidak terbatas per cluster — sehingga top 3 selalu tersedia
# meskipun k cluster berapapun.
# Sertakan deskripsi untuk ditampilkan di UI dan prompt AI.
# ===============================
async def get_top_collaboration_recommendations(
    limit: int = 5, min_similarity: float = 0.3
):
    query = """
    SELECT
        s.inovasi_id_1,
        s.inovasi_id_2,
        s.similarity,
        a.judul_inovasi    AS inovasi_1,
        b.judul_inovasi    AS inovasi_2,
        a.urusan_utama     AS urusan_1,
        b.urusan_utama     AS urusan_2,
        a.tahapan_inovasi  AS tahap_1,
        b.tahapan_inovasi  AS tahap_2,
        a.admin_opd        AS opd_1,
        b.admin_opd        AS opd_2,
        a.deskripsi        AS deskripsi_1,
        b.deskripsi        AS deskripsi_2,
        a.tanggal_penerapan AS tanggal_penerapan_1,
        b.tanggal_penerapan AS tanggal_penerapan_2
    FROM similarity_result s
    JOIN data_inovasi a ON a.id = s.inovasi_id_1
    JOIN data_inovasi b ON b.id = s.inovasi_id_2
    WHERE s.similarity >= :min_similarity
      AND a.admin_opd != b.admin_opd
    ORDER BY s.similarity DESC
    LIMIT :limit
    """

    rows = await database.fetch_all(
        query, {"limit": limit, "min_similarity": min_similarity}
    )

    results = []
    for r in rows:
        r = dict(r)
        results.append(
            {
                "inovasi_id_1": r["inovasi_id_1"],
                "inovasi_id_2": r["inovasi_id_2"],
                "inovasi_1": r["inovasi_1"],
                "inovasi_2": r["inovasi_2"],
                "opd_1": r["opd_1"],
                "opd_2": r["opd_2"],
                "urusan_1": r["urusan_1"],
                "urusan_2": r["urusan_2"],
                "tahap_1": r["tahap_1"],
                "tahap_2": r["tahap_2"],
                "deskripsi_1": r["deskripsi_1"] or "",
                "deskripsi_2": r["deskripsi_2"] or "",
                "tanggal_penerapan_1": (
                    r["tanggal_penerapan_1"].isoformat()
                    if r["tanggal_penerapan_1"]
                    else None
                ),
                "tanggal_penerapan_2": (
                    r["tanggal_penerapan_2"].isoformat()
                    if r["tanggal_penerapan_2"]
                    else None
                ),
                "similarity": r["similarity"],
                "kategori_kemiripan": similarity_label(r["similarity"]),
                "alasan": build_reason(r),
            }
        )

    return results


# ===============================
# REKOMENDASI UNTUK SATU INOVASI
# ===============================
async def recommend_for_inovasi(inovasi_id: int, top_n: int = 5):
    query = """
    SELECT
        s.inovasi_id_1,
        s.inovasi_id_2,
        s.similarity
    FROM similarity_result s
    WHERE s.inovasi_id_1 = :id OR s.inovasi_id_2 = :id
    ORDER BY s.similarity DESC
    LIMIT :limit
    """

    return await database.fetch_all(query, {"id": inovasi_id, "limit": top_n})
