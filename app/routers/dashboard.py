from fastapi import APIRouter
from typing import Optional
from app.database import database

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


# 1. Trend Inovasi per Tahun atau per Bulan
@router.get("/trend")
async def get_trend(tahun: Optional[int] = None):
    """
    Endpoint untuk mendapatkan data trend inovasi.

    - Jika `tahun` tidak diberikan (None): Mengembalikan data per TAHUN (semua tahun)
    - Jika `tahun` diberikan (misal 2022): Mengembalikan data per BULAN untuk tahun tersebut

    Args:
        tahun (Optional[int]): Tahun yang ingin difilter. Jika None, tampilkan semua tahun.

    Returns:
        List: Data trend inovasi per tahun atau per bulan
    """

    if tahun is None:
        # Jika tidak ada parameter tahun, return data per TAHUN
        query = """
        SELECT 
            EXTRACT(YEAR FROM tanggal_penerapan)::int AS tahun,
            COUNT(*) FILTER (WHERE jenis = 'Digital') AS digital,
            COUNT(*) FILTER (WHERE jenis = 'Non Digital') AS nondigital,
            COUNT(*) FILTER (WHERE jenis = 'Teknologi') AS teknologi
        FROM data_inovasi
        WHERE tanggal_penerapan IS NOT NULL
            AND EXTRACT(YEAR FROM tanggal_penerapan) >= 2022
        GROUP BY tahun
        ORDER BY tahun;
        """
        return await database.fetch_all(query)
    else:
        # Jika ada parameter tahun, return data per BULAN untuk tahun tersebut
        query = """
        SELECT 
            EXTRACT(MONTH FROM tanggal_penerapan)::int AS bulan,
            COUNT(*) FILTER (WHERE jenis = 'Digital') AS digital,
            COUNT(*) FILTER (WHERE jenis = 'Non Digital') AS nondigital,
            COUNT(*) FILTER (WHERE jenis = 'Teknologi') AS teknologi
        FROM data_inovasi
        WHERE EXTRACT(YEAR FROM tanggal_penerapan) = :tahun
        GROUP BY bulan
        ORDER BY bulan;
        """
        return await database.fetch_all(query, {"tahun": tahun})


# 2. Maturity / Tahapan Inovasi
@router.get("/maturity")
async def get_maturity():
    query = """
    SELECT 
        tahapan_inovasi AS level, 
        COUNT(*) AS jumlah
    FROM data_inovasi
    GROUP BY tahapan_inovasi
    ORDER BY tahapan_inovasi;
    """
    return await database.fetch_all(query)


# 3. Top OPD
@router.get("/top-opd")
async def get_top_opd():
    query = """
    SELECT 
        admin_opd AS name, 
        COUNT(*) AS jumlah
    FROM data_inovasi
    GROUP BY admin_opd
    ORDER BY jumlah DESC
    LIMIT 5;
    """
    return await database.fetch_all(query)


# 4. Top Urusan
@router.get("/top-urusan")
async def get_top_urusan():
    query = """
    SELECT 
        urusan_utama AS name, 
        COUNT(*) AS jumlah
    FROM data_inovasi
    GROUP BY urusan_utama
    ORDER BY jumlah DESC
    LIMIT 5;
    """
    return await database.fetch_all(query)


# 5. Statistik Ringkas Dashboard
@router.get("/stats")
async def get_stats():
    query = """
    SELECT 
        COUNT(*) AS total_inovasi,
        ROUND(AVG(kematangan)::numeric, 1) AS rata_kematangan,
        COUNT(*) FILTER (WHERE jenis = 'Digital') AS inovasi_digital,
        COUNT(*) FILTER (
            WHERE EXTRACT(YEAR FROM tanggal_penerapan) = EXTRACT(YEAR FROM CURRENT_DATE)
        ) AS inovasi_tahun_ini
    FROM data_inovasi;
    """
    return await database.fetch_one(query)


@router.get("/inovasi-list")
async def get_inovasi_list():
    query = """
    SELECT id, judul_inovasi
    FROM data_inovasi
    WHERE judul_inovasi IS NOT NULL
    ORDER BY judul_inovasi;
    """
    return await database.fetch_all(query)
