from app.database import database


# ==============================
# 1. Cari inovasi berdasarkan judul
# ==============================
async def get_inovasi_by_name(keyword: str):
    query = """
    SELECT id, judul_inovasi, admin_opd, bentuk_inovasi, jenis
    FROM data_inovasi
    WHERE judul_inovasi ILIKE :keyword
    LIMIT 1
    """

    return await database.fetch_one(
        query=query,
        values={"keyword": f"%{keyword}%"},
    )


# ==============================
# 2. Ambil cluster inovasi tertentu
# ==============================
async def get_cluster(id_inovasi: int):
    query = """
    SELECT cluster_id
    FROM clustering_result
    WHERE id_inovasi = :id
    LIMIT 1
    """

    return await database.fetch_one(query, {"id": id_inovasi})


# ==============================
# 3. Metadata cluster (tema besar)
# ==============================
async def get_cluster_metadata(id: int):
    query = """
    SELECT *
    FROM clustering_metadata
    WHERE id = :cid
    LIMIT 1
    """

    return await database.fetch_one(query, {"cid": id})


# ==============================
# 4. Cache insight AI (hemat token)
# ==============================
async def get_cached_insight(id: int):
    query = """
    SELECT summary
    FROM ai_insight_cache
    WHERE id = :id
    LIMIT 1
    """

    return await database.fetch_one(query, {"id": id})
