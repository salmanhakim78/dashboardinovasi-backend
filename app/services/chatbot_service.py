"""
Enhanced Chatbot Service with Hybrid Search (Vector + SQL)
v2.0 - Full data access: ranking OPD, urusan, tahapan, kematangan, tren, dll.
"""

from app.services.ai_service import call_gemini
from app.database import database
from app.services.vector_search_service import (
    hybrid_search_inovasi,
    vector_search_collaboration,
    vector_search_inovasi,
)
from typing import Optional, Dict, List
import json
import re


# ============================================================
# KEYWORD EXTRACTION
# ============================================================
def extract_keywords(question: str) -> List[str]:
    keywords = []
    quoted = re.findall(r'"([^"]+)"', question)
    keywords.extend(quoted)
    single_quoted = re.findall(r"'([^']+)'", question)
    keywords.extend(single_quoted)
    uppercase_words = re.findall(r"\b[A-Z]{2,}(?:\s+[A-Z]+)*\b", question)
    keywords.extend(uppercase_words)
    title_case = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", question)
    keywords.extend(title_case)
    query_patterns = [
        r"apa itu\s+([A-Z\s]+?)(?:\?|$)",
        r"tentang\s+([A-Z\s]+?)(?:\?|$)",
        r"jelaskan\s+([A-Z\s]+?)(?:\?|$)",
        r"info\s+([A-Z\s]+?)(?:\?|$)",
    ]
    for pattern in query_patterns:
        matches = re.findall(pattern, question, re.IGNORECASE)
        keywords.extend([m.strip() for m in matches])
    seen = set()
    unique_keywords = []
    for kw in keywords:
        kw_clean = kw.strip()
        kw_lower = kw_clean.lower()
        if kw_lower not in seen and len(kw_clean) > 2:
            seen.add(kw_lower)
            unique_keywords.append(kw_clean)
    if not unique_keywords:
        caps_sequences = re.findall(r"\b[A-Z][A-Z\s]+\b", question)
        if caps_sequences:
            unique_keywords.append(max(caps_sequences, key=len).strip())
    return unique_keywords


# ============================================================
# QUERY TYPE DETECTION — 9 tipe
# ============================================================
def detect_query_type(question: str) -> str:
    """
    Returns:
      'kolaborasi' | 'ranking_opd' | 'ranking_urusan' | 'tahapan' |
      'kematangan' | 'tren' | 'statistik' | 'inovasi' | 'general'
    """
    q = question.lower()

    if any(
        kw in q
        for kw in [
            "kolaborasi",
            "kerja sama",
            "kerjasama",
            "sinergi",
            "rekomendasi kolaborasi",
            "pasangan",
            "similarity",
            "clustering",
            "cocok",
        ]
    ):
        return "kolaborasi"

    if any(
        kw in q
        for kw in [
            "opd",
            "dinas",
            "badan",
            "instansi",
            "paling aktif",
            "paling banyak",
            "terbanyak",
            "terbesar",
            "peringkat opd",
            "ranking opd",
            "aktif berinovasi",
            "produktif",
        ]
    ):
        return "ranking_opd"

    if any(
        kw in q
        for kw in [
            "urusan",
            "bidang",
            "sektor",
            "pendidikan",
            "kesehatan",
            "infrastruktur",
            "pertanian",
            "sosial",
            "lingkungan",
            "ekonomi",
            "urusan apa",
            "bidang apa",
            "kategori",
        ]
    ):
        return "ranking_urusan"

    if any(
        kw in q
        for kw in [
            "tahapan",
            "tahap",
            "penerapan",
            "pengembangan",
            "inisiasi",
            "sudah diterapkan",
            "distribusi tahap",
            "fase",
        ]
    ):
        return "tahapan"

    # FIX: Tambahkan variasi frasa "siap replikasi" agar tidak terlewat
    if any(
        kw in q
        for kw in [
            "kematangan",
            "matang",
            "siap replikasi",
            "siap direplikasi",
            "siap untuk direplikasi",
            "paling siap",
            "paling siap direplikasi",
            "paling siap untuk direplikasi",
            "inovatif",
            "kurang inovatif",
            "sangat inovatif",
            "skor kematangan",
            "level inovasi",
        ]
    ):
        return "kematangan"

    if any(
        kw in q
        for kw in [
            "tren",
            "trend",
            "tahun",
            "pertumbuhan",
            "perkembangan",
            "terbaru",
            "terkini",
            "berapa tahun",
            "kapan",
            "sejarah",
        ]
    ):
        return "tren"

    if any(
        kw in q
        for kw in [
            "berapa",
            "jumlah",
            "total",
            "statistik",
            "banyak",
            "angka",
            "data",
        ]
    ):
        return "statistik"

    if any(
        kw in q
        for kw in [
            "apa itu",
            "jelaskan",
            "tentang",
            "info",
            "detail",
            "inovasi",
            "ceritakan",
            "bagaimana",
            "seperti apa",
        ]
    ):
        return "inovasi"

    return "general"


# ============================================================
# HELPER: kematangan label dari skor
# ============================================================
def kematangan_label(skor) -> str:
    try:
        s = float(skor)
        if s < 45:
            return "Kurang Inovatif"
        elif s < 65:
            return "Inovatif"
        else:
            return "Sangat Inovatif"
    except (TypeError, ValueError):
        return str(skor)


# ============================================================
# DB FUNCTIONS
# ============================================================


async def get_statistics() -> Dict:
    try:
        if not database.is_connected:
            return {}
        result = await database.fetch_one(
            """
            SELECT
                COUNT(*) AS total_inovasi,
                COUNT(*) FILTER (WHERE jenis = 'Digital') AS inovasi_digital,
                COUNT(*) FILTER (WHERE jenis != 'Digital') AS inovasi_non_digital,
                COUNT(*) FILTER (
                    WHERE EXTRACT(YEAR FROM tanggal_penerapan) = EXTRACT(YEAR FROM CURRENT_DATE)
                ) AS inovasi_tahun_ini,
                ROUND(AVG(kematangan)::numeric, 1) AS rata_kematangan,
                COUNT(DISTINCT admin_opd) AS jumlah_opd,
                COUNT(DISTINCT urusan_utama) AS jumlah_urusan,
                COUNT(DISTINCT pemda) AS jumlah_pemda
            FROM data_inovasi
        """
        )
        return dict(result) if result else {}
    except Exception as e:
        print(f"❌ get_statistics: {e}")
        return {}


async def get_top_opd(limit: int = 10) -> List[Dict]:
    try:
        if not database.is_connected:
            return []
        results = await database.fetch_all(
            f"""
            SELECT
                admin_opd,
                COUNT(*) AS jumlah_inovasi,
                ROUND(AVG(kematangan)::numeric, 1) AS rata_kematangan,
                COUNT(*) FILTER (WHERE tahapan_inovasi ILIKE '%Penerapan%') AS sudah_diterapkan,
                COUNT(*) FILTER (WHERE jenis = 'Digital') AS inovasi_digital
            FROM data_inovasi
            WHERE admin_opd IS NOT NULL AND admin_opd != ''
            GROUP BY admin_opd
            ORDER BY jumlah_inovasi DESC
            LIMIT {limit}
        """
        )
        return [dict(r) for r in results] if results else []
    except Exception as e:
        print(f"❌ get_top_opd: {e}")
        return []


async def get_top_urusan(limit: int = 10) -> List[Dict]:
    try:
        if not database.is_connected:
            return []
        results = await database.fetch_all(
            f"""
            SELECT
                urusan_utama,
                COUNT(*) AS jumlah_inovasi,
                ROUND(AVG(kematangan)::numeric, 1) AS rata_kematangan,
                COUNT(*) FILTER (WHERE jenis = 'Digital') AS inovasi_digital
            FROM data_inovasi
            WHERE urusan_utama IS NOT NULL AND urusan_utama != ''
            GROUP BY urusan_utama
            ORDER BY jumlah_inovasi DESC
            LIMIT {limit}
        """
        )
        return [dict(r) for r in results] if results else []
    except Exception as e:
        print(f"❌ get_top_urusan: {e}")
        return []


async def get_tahapan_distribution() -> List[Dict]:
    try:
        if not database.is_connected:
            return []
        results = await database.fetch_all(
            """
            SELECT
                tahapan_inovasi,
                COUNT(*) AS jumlah,
                ROUND(AVG(kematangan)::numeric, 1) AS rata_kematangan
            FROM data_inovasi
            WHERE tahapan_inovasi IS NOT NULL AND tahapan_inovasi != ''
            GROUP BY tahapan_inovasi
            ORDER BY jumlah DESC
        """
        )
        return [dict(r) for r in results] if results else []
    except Exception as e:
        print(f"❌ get_tahapan_distribution: {e}")
        return []


async def get_kematangan_distribution() -> Dict:
    try:
        if not database.is_connected:
            return {}
        result = await database.fetch_one(
            """
            SELECT
                COUNT(*) FILTER (WHERE kematangan < 45) AS kurang_inovatif,
                COUNT(*) FILTER (WHERE kematangan >= 45 AND kematangan < 65) AS inovatif,
                COUNT(*) FILTER (WHERE kematangan >= 65) AS sangat_inovatif,
                ROUND(MIN(kematangan)::numeric, 1) AS skor_min,
                ROUND(MAX(kematangan)::numeric, 1) AS skor_max,
                ROUND(AVG(kematangan)::numeric, 1) AS skor_rata
            FROM data_inovasi
            WHERE kematangan IS NOT NULL
        """
        )
        return dict(result) if result else {}
    except Exception as e:
        print(f"❌ get_kematangan_distribution: {e}")
        return {}


async def get_tren_per_tahun() -> List[Dict]:
    try:
        if not database.is_connected:
            return []
        results = await database.fetch_all(
            """
            SELECT
                EXTRACT(YEAR FROM tanggal_penerapan)::int AS tahun,
                COUNT(*) AS jumlah_inovasi,
                COUNT(*) FILTER (WHERE jenis = 'Digital') AS digital,
                ROUND(AVG(kematangan)::numeric, 1) AS rata_kematangan
            FROM data_inovasi
            WHERE tanggal_penerapan IS NOT NULL
            GROUP BY tahun
            ORDER BY tahun DESC
            LIMIT 8
        """
        )
        return [dict(r) for r in results] if results else []
    except Exception as e:
        print(f"❌ get_tren_per_tahun: {e}")
        return []


async def get_inovasi_by_urusan(urusan: str, limit: int = 5) -> List[Dict]:
    try:
        if not database.is_connected:
            return []
        results = await database.fetch_all(
            """
            SELECT judul_inovasi, admin_opd, tahapan_inovasi, kematangan, jenis, pemda
            FROM data_inovasi
            WHERE urusan_utama ILIKE :urusan
            ORDER BY kematangan DESC
            LIMIT :limit
        """,
            {"urusan": f"%{urusan}%", "limit": limit},
        )
        return [dict(r) for r in results] if results else []
    except Exception as e:
        print(f"❌ get_inovasi_by_urusan: {e}")
        return []


async def get_inovasi_terbaru(limit: int = 5) -> List[Dict]:
    try:
        if not database.is_connected:
            return []
        results = await database.fetch_all(
            """
            SELECT judul_inovasi, admin_opd, urusan_utama,
                   tahapan_inovasi, kematangan, jenis, tanggal_penerapan, pemda
            FROM data_inovasi
            WHERE tanggal_penerapan IS NOT NULL
            ORDER BY tanggal_penerapan DESC
            LIMIT :limit
        """,
            {"limit": limit},
        )
        return [dict(r) for r in results] if results else []
    except Exception as e:
        print(f"❌ get_inovasi_terbaru: {e}")
        return []


async def get_top_inovasi_matang(limit: int = 5) -> List[Dict]:
    try:
        if not database.is_connected:
            return []
        results = await database.fetch_all(
            """
            SELECT judul_inovasi, admin_opd, urusan_utama,
                   tahapan_inovasi, kematangan, jenis, pemda
            FROM data_inovasi
            WHERE kematangan IS NOT NULL
            ORDER BY kematangan DESC
            LIMIT :limit
        """,
            {"limit": limit},
        )
        return [dict(r) for r in results] if results else []
    except Exception as e:
        print(f"❌ get_top_inovasi_matang: {e}")
        return []


async def get_collaboration_data(
    inovasi_id: Optional[int] = None, limit: int = 3
) -> List[Dict]:
    try:
        if not database.is_connected:
            return []
        if inovasi_id:
            results = await database.fetch_all(
                """
                SELECT s.similarity,
                    a.judul_inovasi AS inovasi_1, b.judul_inovasi AS inovasi_2,
                    a.admin_opd AS opd_1, b.admin_opd AS opd_2,
                    a.urusan_utama AS urusan, s.cluster_id
                FROM similarity_result s
                JOIN data_inovasi a ON a.id = s.inovasi_id_1
                JOIN data_inovasi b ON b.id = s.inovasi_id_2
                WHERE s.inovasi_id_1 = :id OR s.inovasi_id_2 = :id
                ORDER BY s.similarity DESC LIMIT :limit
            """,
                {"id": inovasi_id, "limit": limit},
            )
            if results:
                return [dict(r) for r in results]
            try:
                vector_results = await vector_search_collaboration(
                    inovasi_id, top_k=limit, min_similarity=0.3
                )
                if vector_results:
                    return [
                        {
                            "similarity": vr["similarity_score"],
                            "inovasi_1": "Target Inovasi",
                            "inovasi_2": vr["judul_inovasi"],
                            "opd_1": "-",
                            "opd_2": vr.get("admin_opd", "-"),
                            "urusan": vr.get("urusan_utama", "-"),
                            "cluster_id": None,
                        }
                        for vr in vector_results
                    ]
            except Exception as ve:
                print(f"⚠️ Vector collab search: {ve}")
            return []
        else:
            results = await database.fetch_all(
                """
                SELECT s.similarity,
                    a.judul_inovasi AS inovasi_1, b.judul_inovasi AS inovasi_2,
                    a.admin_opd AS opd_1, b.admin_opd AS opd_2,
                    a.urusan_utama AS urusan, s.cluster_id
                FROM similarity_result s
                JOIN data_inovasi a ON a.id = s.inovasi_id_1
                JOIN data_inovasi b ON b.id = s.inovasi_id_2
                WHERE a.admin_opd != b.admin_opd
                ORDER BY s.similarity DESC LIMIT :limit
            """,
                {"limit": limit},
            )
            return [dict(r) for r in results] if results else []
    except Exception as e:
        print(f"❌ get_collaboration_data: {e}")
        return []


async def get_cached_dashboard_insight() -> Optional[str]:
    try:
        if not database.is_connected:
            return None
        cache = await database.fetch_one(
            """
            SELECT insight_data FROM ai_insight_cache
            WHERE insight_type = 'dashboard'
            ORDER BY created_at DESC LIMIT 1
        """
        )
        if cache and cache["insight_data"]:
            raw = cache["insight_data"]
            insights = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(insights, list):
                return " ".join(
                    [
                        item.get("text", "")
                        for item in insights[:3]
                        if isinstance(item, dict)
                    ]
                )
            return str(insights)
        return None
    except Exception as e:
        if "does not exist" not in str(e):
            print(f"⚠️ get_cached_dashboard_insight: {e}")
        return None


async def fetch_inovasi_full(inovasi_id: int) -> Optional[Dict]:
    try:
        if not database.is_connected:
            return None
        result = await database.fetch_one(
            """
            SELECT id, judul_inovasi, pemda, admin_opd, inisiator, nama_inisiator,
                   bentuk_inovasi, jenis, asta_cipta, urusan_utama,
                   urusan_lain_yang_beririsan, tahapan_inovasi,
                   label_kematangan, kematangan, tanggal_penerapan,
                   tanggal_pengembangan, tanggal_input, video, link_video,
                   lat, lon, deskripsi
            FROM data_inovasi WHERE id = :id
        """,
            {"id": inovasi_id},
        )
        return dict(result) if result else None
    except Exception as e:
        print(f"❌ fetch_inovasi_full: {e}")
        return None


# ============================================================
# MAIN CHATBOT FUNCTION
# ============================================================
async def chatbot_answer(question: str) -> str:
    print(f"\n{'='*60}\nCHATBOT QUERY: {question}\n{'='*60}")

    if not database.is_connected:
        return (
            "Maaf, sistem sedang dalam pemeliharaan. Silakan coba beberapa saat lagi."
        )

    try:
        keywords = extract_keywords(question)
        print(f"🔍 Keywords: {keywords}")

        query_type = detect_query_type(question)
        print(f"🔍 Query type: {query_type}")

        context_data = {"found_in_db": False, "data_type": query_type, "content": {}}

        # ── Kolaborasi ──────────────────────────────────────────
        if query_type == "kolaborasi":
            inovasi = None
            if keywords:
                try:
                    inovasi = await hybrid_search_inovasi(question, keywords, top_k=3)
                except Exception as e:
                    print(f"⚠️ Hybrid search: {e}")
            if inovasi:
                full_data = await fetch_inovasi_full(inovasi["id"])
                if full_data:
                    inovasi.update(full_data)
                collab_data = await get_collaboration_data(inovasi_id=inovasi["id"])
                context_data["found_in_db"] = True
                context_data["content"] = {
                    "inovasi": inovasi,
                    "kolaborasi": collab_data,
                }
                if "match_type" in inovasi:
                    context_data["content"]["search_method"] = inovasi["match_type"]
                    context_data["content"]["match_score"] = inovasi.get(
                        "match_score", 0
                    )
            else:
                collab_data = await get_collaboration_data(limit=5)
                if collab_data:
                    context_data["found_in_db"] = True
                    context_data["content"] = {"kolaborasi": collab_data}

        # ── Ranking OPD ─────────────────────────────────────────
        elif query_type == "ranking_opd":
            top_opd = await get_top_opd(limit=10)
            stats = await get_statistics()
            if top_opd:
                context_data["found_in_db"] = True
                context_data["content"] = {"top_opd": top_opd, "statistik": stats}

        # ── Ranking Urusan ──────────────────────────────────────
        elif query_type == "ranking_urusan":
            top_urusan = await get_top_urusan(limit=10)
            stats = await get_statistics()
            urusan_contoh = None
            for kw in keywords:
                inovasi_urusan = await get_inovasi_by_urusan(kw, limit=5)
                if inovasi_urusan:
                    urusan_contoh = {"keyword": kw, "inovasi": inovasi_urusan}
                    break
            if top_urusan:
                context_data["found_in_db"] = True
                context_data["content"] = {"top_urusan": top_urusan, "statistik": stats}
                if urusan_contoh:
                    context_data["content"]["inovasi_urusan"] = urusan_contoh

        # ── Tahapan ─────────────────────────────────────────────
        elif query_type == "tahapan":
            tahapan = await get_tahapan_distribution()
            stats = await get_statistics()
            if tahapan:
                context_data["found_in_db"] = True
                context_data["content"] = {"tahapan": tahapan, "statistik": stats}

        # ── Kematangan ──────────────────────────────────────────
        elif query_type == "kematangan":
            kematangan_dist = await get_kematangan_distribution()
            top_matang = await get_top_inovasi_matang(limit=5)
            stats = await get_statistics()
            if kematangan_dist:
                context_data["found_in_db"] = True
                context_data["content"] = {
                    "kematangan_dist": kematangan_dist,
                    "top_matang": top_matang,
                    "statistik": stats,
                }

        # ── Tren ────────────────────────────────────────────────
        elif query_type == "tren":
            tren = await get_tren_per_tahun()
            inovasi_terbaru = await get_inovasi_terbaru(limit=5)
            stats = await get_statistics()
            if tren:
                context_data["found_in_db"] = True
                context_data["content"] = {
                    "tren": tren,
                    "inovasi_terbaru": inovasi_terbaru,
                    "statistik": stats,
                }

        # ── Statistik Umum ──────────────────────────────────────
        elif query_type == "statistik":
            stats = await get_statistics()
            top_opd = await get_top_opd(limit=5)
            top_urusan = await get_top_urusan(limit=5)
            tahapan = await get_tahapan_distribution()
            if stats:
                context_data["found_in_db"] = True
                context_data["content"] = {
                    "statistik": stats,
                    "top_opd": top_opd,
                    "top_urusan": top_urusan,
                    "tahapan": tahapan,
                }

        # ── Inovasi Spesifik ────────────────────────────────────
        elif query_type == "inovasi":
            inovasi = None
            if keywords or question:
                try:
                    search_query = question if not keywords else " ".join(keywords)
                    inovasi = await hybrid_search_inovasi(
                        search_query, keywords, top_k=3
                    )
                except Exception as e:
                    print(f"⚠️ Hybrid search: {e}")
            if not inovasi and (keywords or question):
                try:
                    search_query = question if not keywords else " ".join(keywords)
                    vector_results = await vector_search_inovasi(
                        search_query, top_k=3, min_similarity=0.15
                    )
                    if vector_results:
                        inovasi = vector_results[0]
                        inovasi["match_type"] = "semantic_fuzzy"
                        inovasi["match_score"] = inovasi["similarity_score"]
                except Exception as e:
                    print(f"⚠️ Vector search: {e}")
            if inovasi:
                full_data = await fetch_inovasi_full(inovasi["id"])
                if full_data:
                    inovasi.update(full_data)
                context_data["found_in_db"] = True
                context_data["content"] = {"inovasi": inovasi}
                if "match_type" in inovasi:
                    context_data["content"]["search_method"] = inovasi["match_type"]
                    context_data["content"]["match_score"] = inovasi.get(
                        "match_score", 0
                    )

        # ── General — sertakan data umum ───────────────────────
        else:
            stats = await get_statistics()
            top_opd = await get_top_opd(limit=5)
            inovasi_terbaru = await get_inovasi_terbaru(limit=3)
            if stats:
                context_data["found_in_db"] = True
                context_data["content"] = {
                    "statistik": stats,
                    "top_opd": top_opd,
                    "inovasi_terbaru": inovasi_terbaru,
                }

        # ── Dashboard Insight selalu disertakan ─────────────────
        dashboard_insight = await get_cached_dashboard_insight()
        if dashboard_insight:
            context_data["content"]["dashboard_insight"] = dashboard_insight

        prompt = build_chatbot_prompt(question, context_data)

        try:
            answer = call_gemini(prompt, mode="chatbot")
            return answer.strip()
        except Exception as e:
            print(f"❌ Chatbot AI Error: {e}")
            return "Maaf, terjadi kesalahan saat memproses pertanyaan kamu. Silakan coba lagi ya! 😊"

    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        return "Wah, ada kesalahan sistem nih. Coba lagi ya, atau hubungi admin kalau masih bermasalah! 🙏"


# ============================================================
# PROMPT BUILDER
# ============================================================
def build_chatbot_prompt(question: str, context_data: Dict) -> str:

    system_role = """
Kamu adalah AI Assistant BRIDA (Badan Riset dan Inovasi Daerah) Provinsi Jawa Timur.
Tugas kamu adalah membantu masyarakat umum memahami inovasi daerah di Jawa Timur.

ATURAN TINGKAT KEMATANGAN INOVASI (WAJIB DIIKUTI):
- Skor   0 – 44,99  → "Kurang Inovatif"
- Skor  45 – 64,99  → "Inovatif"
- Skor  65 – 111    → "Sangat Inovatif"
Selalu gunakan kategori ini. Jangan gunakan label lain.

GAYA KOMUNIKASI:
- Ramah dan mudah dipahami (seperti berbicara dengan teman)
- Akurat berdasarkan data yang diberikan, JANGAN mengarang
- Gunakan bahasa natural, tidak kaku
- Boleh pakai emoji relevan (💡, ✨, 📊, 🚀, 🏥, 🎓, 🏆, dll)
- Gunakan "kamu" bukan "Anda"
- Sapa dengan: "Halo!", "Hai!", atau langsung jawab
- Akhiri dengan encouraging: "Semoga membantu!", "Ada yang ingin ditanyakan lagi?"
- JANGAN pakai "Yang Terhormat", "Hormat kami", "Atas perhatiannya"
- Format list dengan emoji jika data banyak
- Field bernilai "-" atau null tidak perlu disebutkan
"""

    if not context_data["found_in_db"]:
        db_context = """
CATATAN: Data spesifik tidak ditemukan.
Sampaikan dengan ramah, tawarkan bantuan untuk pertanyaan lain seperti:
- "OPD mana yang paling aktif berinovasi?"
- "Berapa total inovasi di Jatim?"
- "Inovasi di bidang kesehatan apa saja?"
- "Inovasi mana yang paling siap direplikasi?"
"""
    else:
        content = context_data["content"]
        db_context = ""

        # Search quality
        if "search_method" in content:
            method = content["search_method"]
            score = content.get("match_score", 0)
            if method == "exact":
                db_context += "(✅ Exact match)\n"
            elif method == "semantic":
                db_context += f"(🔍 Semantik - kesesuaian {score:.0%})\n"
            elif method == "semantic_fuzzy":
                db_context += f"⚠️ Hasil terdekat (kesesuaian {score:.0%}). Sampaikan friendly bahwa ini mungkin bukan exact match.\n"
            elif method == "hybrid":
                db_context += f"(🎯 Gabungan - kesesuaian {score:.0%})\n"

        # Data Inovasi Spesifik — SELURUH KOLOM
        if "inovasi" in content:
            inv = content["inovasi"]
            deskripsi_text = inv.get("deskripsi", "") or ""
            if len(deskripsi_text) > 1500:
                deskripsi_text = deskripsi_text[:1500] + "..."
            skor = inv.get("kematangan")
            label = (
                kematangan_label(skor)
                if skor is not None
                else inv.get("label_kematangan", "-")
            )
            db_context += f"""
DATA INOVASI:
- Judul: {inv.get('judul_inovasi', '-')}
- Pemerintah Daerah: {inv.get('pemda', '-')}
- OPD: {inv.get('admin_opd', '-')}
- Inisiator: {inv.get('inisiator', '-')} ({inv.get('nama_inisiator', '-')})
- Bentuk Inovasi: {inv.get('bentuk_inovasi', '-')}
- Jenis: {inv.get('jenis', '-')}
- Asta Cita: {inv.get('asta_cipta', '-')}
- Urusan Utama: {inv.get('urusan_utama', '-')}
- Urusan Lain yang Beririsan: {inv.get('urusan_lain_yang_beririsan', '-')}
- Tahapan: {inv.get('tahapan_inovasi', '-')}
- Tingkat Kematangan: {label} (Skor: {skor if skor is not None else '-'})
- Tanggal Penerapan: {inv.get('tanggal_penerapan', '-')}
- Tanggal Pengembangan: {inv.get('tanggal_pengembangan', '-')}
- Tanggal Input: {inv.get('tanggal_input', '-')}
- Video: {'Ada - ' + str(inv.get('link_video', '')) if inv.get('video') else 'Tidak ada'}
- Koordinat: {f"Lat {inv.get('lat')}, Lon {inv.get('lon')}" if inv.get('lat') and inv.get('lon') else '-'}

DESKRIPSI LENGKAP:
{deskripsi_text if deskripsi_text else '(Deskripsi tidak tersedia)'}

Gunakan DESKRIPSI LENGKAP sebagai sumber utama penjelasan inovasi ini.
"""

        # Kolaborasi
        if "kolaborasi" in content and content["kolaborasi"]:
            db_context += "\nDATA KOLABORASI POTENSIAL:\n"
            for i, c in enumerate(content["kolaborasi"][:3], 1):
                db_context += f"{i}. {c['inovasi_1']} ↔ {c['inovasi_2']}\n"
                db_context += f"   OPD: {c['opd_1']} × {c['opd_2']} | Match: {c['similarity']:.0%}\n"

        # Top OPD
        if "top_opd" in content and content["top_opd"]:
            db_context += "\nRANKING OPD PALING AKTIF BERINOVASI:\n"
            for i, opd in enumerate(content["top_opd"], 1):
                db_context += (
                    f"{i}. {opd['admin_opd']} — {opd['jumlah_inovasi']} inovasi"
                    f" | Digital: {opd.get('inovasi_digital', 0)}"
                    f" | Diterapkan: {opd.get('sudah_diterapkan', 0)}"
                    f" | Rata kematangan: {opd.get('rata_kematangan', '-')}\n"
                )

        # Top Urusan
        if "top_urusan" in content and content["top_urusan"]:
            db_context += "\nDISTRIBUSI INOVASI PER BIDANG URUSAN:\n"
            for i, u in enumerate(content["top_urusan"], 1):
                db_context += (
                    f"{i}. {u['urusan_utama']} — {u['jumlah_inovasi']} inovasi"
                    f" | Digital: {u.get('inovasi_digital', 0)}"
                    f" | Rata kematangan: {u.get('rata_kematangan', '-')}\n"
                )

        # Inovasi per Urusan
        if "inovasi_urusan" in content:
            iu = content["inovasi_urusan"]
            db_context += f"\nCONTOH INOVASI DI BIDANG '{iu['keyword'].upper()}':\n"
            for inv in iu["inovasi"]:
                skor = inv.get("kematangan")
                db_context += (
                    f"- {inv['judul_inovasi']} ({inv.get('admin_opd', '-')})"
                    f" | {inv.get('tahapan_inovasi', '-')}"
                    f" | {kematangan_label(skor)} ({skor})\n"
                )

        # Tahapan
        if "tahapan" in content and content["tahapan"]:
            db_context += "\nDISTRIBUSI TAHAPAN INOVASI:\n"
            for t in content["tahapan"]:
                db_context += f"- {t['tahapan_inovasi']}: {t['jumlah']} inovasi (rata kematangan: {t.get('rata_kematangan', '-')})\n"

        # Kematangan Distribusi
        if "kematangan_dist" in content:
            kd = content["kematangan_dist"]
            db_context += f"""
DISTRIBUSI KEMATANGAN INOVASI:
- Kurang Inovatif  (0–44,99)  : {kd.get('kurang_inovatif', 0)} inovasi
- Inovatif         (45–64,99) : {kd.get('inovatif', 0)} inovasi
- Sangat Inovatif  (65–111)   : {kd.get('sangat_inovatif', 0)} inovasi
- Skor: min={kd.get('skor_min', '-')}, max={kd.get('skor_max', '-')}, rata={kd.get('skor_rata', '-')}
"""

        # Top Inovasi Matang
        if "top_matang" in content and content["top_matang"]:
            db_context += "\nINOVASI KEMATANGAN TERTINGGI (siap replikasi):\n"
            for i, inv in enumerate(content["top_matang"], 1):
                skor = inv.get("kematangan")
                db_context += (
                    f"{i}. {inv['judul_inovasi']}\n"
                    f"   OPD: {inv.get('admin_opd', '-')}\n"
                    f"   Skor Kematangan: {skor} ({kematangan_label(skor)})\n"
                    f"   Tahapan: {inv.get('tahapan_inovasi', '-')}\n"
                    f"   Urusan: {inv.get('urusan_utama', '-')}\n\n"
                )

        # Tren
        if "tren" in content and content["tren"]:
            db_context += "\nTREN INOVASI PER TAHUN:\n"
            for t in content["tren"]:
                db_context += (
                    f"- {t['tahun']}: {t['jumlah_inovasi']} inovasi"
                    f" | Digital: {t.get('digital', 0)}"
                    f" | Rata kematangan: {t.get('rata_kematangan', '-')}\n"
                )

        # Inovasi Terbaru
        if "inovasi_terbaru" in content and content["inovasi_terbaru"]:
            db_context += "\nINOVASI TERBARU:\n"
            for inv in content["inovasi_terbaru"]:
                db_context += (
                    f"- {inv['judul_inovasi']} ({inv.get('admin_opd', '-')})"
                    f" | {inv.get('urusan_utama', '-')}"
                    f" | Diterapkan: {inv.get('tanggal_penerapan', '-')}\n"
                )

        # Statistik Umum
        if "statistik" in content and content["statistik"]:
            s = content["statistik"]
            db_context += f"""
STATISTIK UMUM INOVASI JATIM:
- Total inovasi    : {s.get('total_inovasi', 0)}
- Inovasi digital  : {s.get('inovasi_digital', 0)}
- Non-digital      : {s.get('inovasi_non_digital', 0)}
- Inovasi tahun ini: {s.get('inovasi_tahun_ini', 0)}
- Rata kematangan  : {s.get('rata_kematangan', 0)}
- Jumlah OPD aktif : {s.get('jumlah_opd', 0)}
- Jumlah urusan    : {s.get('jumlah_urusan', 0)}
- Jumlah pemda     : {s.get('jumlah_pemda', 0)}
"""

        # Dashboard Insight
        if "dashboard_insight" in content:
            db_context += f"\nINSIGHT TERKINI:\n{content['dashboard_insight']}\n"

    final_prompt = f"""{system_role}

PERTANYAAN USER:
{question}

DATA DARI DATABASE:
{db_context}

INSTRUKSI:
1. Jawab FRIENDLY dan CASUAL, pakai emoji relevan
2. Gunakan "kamu" bukan "Anda"
3. JANGAN pakai "Yang Terhormat", "Hormat kami", dll
4. Akhiri dengan encouraging statement
5. Untuk daftar inovasi, gunakan FORMAT BERNOMOR (1. 2. 3.) — tiap inovasi tampilkan nama, OPD, dan skor kematangan dalam kalimat singkat yang mengalir, BUKAN bullet pendek terpisah-pisah
6. JANGAN mengarang data yang tidak ada di atas
7. Fokus pada informasi paling relevan dengan pertanyaan
8. Field "-" atau null tidak perlu disebutkan
9. Untuk kematangan WAJIB gunakan: Kurang Inovatif / Inovatif / Sangat Inovatif
10. Hindari memecah satu inovasi menjadi beberapa baris bullet — satukan dalam satu paragraf atau satu nomor

JAWABAN:
"""
    return final_prompt
