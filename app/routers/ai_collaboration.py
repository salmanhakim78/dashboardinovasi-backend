from fastapi import APIRouter, HTTPException
from app.services.ai_service import call_gemini
from app.services.insight_builder import build_input_collaboration_prompt
from app.database import database
from app.services.clustering_service import embedding_model
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import json

router = APIRouter(prefix="/ai-input-collaboration", tags=["AI Input Collaboration"])


# ===============================
# HITUNG SKOR BERDASARKAN COSINE SIMILARITY DESKRIPSI
# Menggunakan model embedding yang sama dengan clustering_service
# agar konsisten. Fallback ke judul jika deskripsi kosong.
# Return float 0.0 - 1.0
# ===============================
def calculate_description_similarity(inn1: dict, inn2: dict) -> float:
    teks_1 = (inn1.get("deskripsi") or "").strip() or (
        inn1.get("judul_inovasi") or ""
    ).strip()
    teks_2 = (inn2.get("deskripsi") or "").strip() or (
        inn2.get("judul_inovasi") or ""
    ).strip()

    if not teks_1 or not teks_2:
        return 0.0

    embeddings = embedding_model.encode(
        [teks_1, teks_2], show_progress_bar=False, batch_size=2
    )
    score = float(cosine_similarity([embeddings[0]], [embeddings[1]])[0][0])

    # Clamp ke range 0.0 - 1.0 untuk keamanan
    return round(max(0.0, min(1.0, score)), 4)


def build_fallback_ai_result(inn1: dict, inn2: dict, score: float) -> dict:
    """Fallback result ketika Gemini API tidak tersedia."""
    judul1 = inn1.get("judul_inovasi", "Inovasi 1")
    judul2 = inn2.get("judul_inovasi", "Inovasi 2")
    urusan1 = inn1.get("urusan_utama", "-")
    urusan2 = inn2.get("urusan_utama", "-")
    tahap1 = inn1.get("tahapan_inovasi", "-")
    tahap2 = inn2.get("tahapan_inovasi", "-")

    if score >= 0.85:
        tingkat = "Kolaborasi Tinggi"
    elif score >= 0.65:
        tingkat = "Kolaborasi Sedang"
    else:
        tingkat = "Kolaborasi Dasar"

    judul_kolaborasi = f"Sinergi {judul1[:40]}... & {judul2[:40]}..."

    if urusan1 == urusan2:
        alasan = (
            f"Kedua inovasi bergerak di bidang urusan yang sama yaitu {urusan1}, "
            f"sehingga memiliki potensi sinergi yang kuat dalam hal sumber daya, "
            f"target penerima manfaat, dan pendekatan implementasi."
        )
    else:
        alasan = (
            f"Meskipun bergerak di bidang urusan yang berbeda ({urusan1} dan {urusan2}), "
            f"kedua inovasi memiliki kesamaan konteks dan pendekatan yang dapat "
            f"saling melengkapi untuk menciptakan dampak yang lebih luas."
        )

    manfaat = [
        f"Berbagi sumber daya dan infrastruktur antara {inn1.get('admin_opd', 'OPD 1')} dan {inn2.get('admin_opd', 'OPD 2')}",
        "Memperluas jangkauan layanan kepada masyarakat melalui pendekatan terpadu",
        f"Mengoptimalkan tahap implementasi yang saat ini berada di tahap {tahap1} dan {tahap2}",
        "Meningkatkan efisiensi anggaran melalui kolaborasi lintas OPD",
    ]

    dampak = [
        "Peningkatan kualitas layanan publik yang lebih terintegrasi",
        "Percepatan inovasi melalui transfer pengetahuan antar OPD",
        f"Potensi replikasi ke daerah lain dengan skor kecocokan {round(score * 100)}%",
    ]

    return {
        "judul_kolaborasi": judul_kolaborasi,
        "alasan_sinergi": alasan,
        "manfaat_kolaborasi": manfaat,
        "potensi_dampak": dampak,
        "tingkat_kolaborasi": tingkat,
    }


@router.get("/simulate")
async def simulate_ai_collaboration(inovasi_1_id: int, inovasi_2_id: int):

    # Ambil data lengkap termasuk deskripsi
    inovasi_1 = await database.fetch_one(
        """
        SELECT id, judul_inovasi, admin_opd, urusan_utama, jenis,
               tahapan_inovasi, label_kematangan, deskripsi, tanggal_penerapan
        FROM data_inovasi WHERE id = :id
        """,
        {"id": inovasi_1_id},
    )

    inovasi_2 = await database.fetch_one(
        """
        SELECT id, judul_inovasi, admin_opd, urusan_utama, jenis,
               tahapan_inovasi, label_kematangan, deskripsi, tanggal_penerapan
        FROM data_inovasi WHERE id = :id
        """,
        {"id": inovasi_2_id},
    )

    if not inovasi_1 or not inovasi_2:
        raise HTTPException(status_code=404, detail="Data inovasi tidak ditemukan")

    inn1 = dict(inovasi_1)
    inn2 = dict(inovasi_2)

    # ✅ Cek dulu di similarity_result (hasil clustering), lebih cepat & konsisten
    # Coba kedua urutan id karena pasangan bisa tersimpan sebagai (a,b) atau (b,a)
    existing = await database.fetch_one(
        """
        SELECT similarity FROM similarity_result
        WHERE (inovasi_id_1 = :id1 AND inovasi_id_2 = :id2)
           OR (inovasi_id_1 = :id2 AND inovasi_id_2 = :id1)
        ORDER BY similarity DESC
        LIMIT 1
        """,
        {"id1": inovasi_1_id, "id2": inovasi_2_id},
    )

    if existing:
        score = round(float(existing["similarity"]), 4)
        print(f"✅ Skor dari similarity_result: {score}")
    else:
        # Fallback: hitung cosine similarity dari embedding deskripsi
        score = calculate_description_similarity(inn1, inn2)
        print(f"⚙️ Skor dihitung dari embedding: {score}")

    ai_result = None
    used_fallback = False

    try:
        prompt = build_input_collaboration_prompt(inn1, inn2, score)
        ai_response = call_gemini(prompt, mode="collaboration")

        try:
            ai_result = json.loads(
                ai_response.strip().replace("```json", "").replace("```", "")
            )
        except (json.JSONDecodeError, Exception) as parse_err:
            print(f"⚠️ JSON parse error dari Gemini: {parse_err}")
            ai_result = None

    except Exception as gemini_err:
        print(f"⚠️ Gemini API error (menggunakan fallback): {gemini_err}")
        ai_result = None

    if ai_result is None:
        ai_result = build_fallback_ai_result(inn1, inn2, score)
        used_fallback = True

    return {
        "inovasi_1": {
            "id": inn1["id"],
            "judul": inn1.get("judul_inovasi"),
            "opd": inn1.get("admin_opd") or "-",
            "urusan": inn1.get("urusan_utama") or "-",
            "tahap": inn1.get("tahapan_inovasi") or "-",
            "deskripsi": inn1.get("deskripsi") or "",
            "tanggal_penerapan": (
                inn1["tanggal_penerapan"].isoformat()
                if inn1.get("tanggal_penerapan")
                else None
            ),
        },
        "inovasi_2": {
            "id": inn2["id"],
            "judul": inn2.get("judul_inovasi"),
            "opd": inn2.get("admin_opd") or "-",
            "urusan": inn2.get("urusan_utama") or "-",
            "tahap": inn2.get("tahapan_inovasi") or "-",
            "deskripsi": inn2.get("deskripsi") or "",
            "tanggal_penerapan": (
                inn2["tanggal_penerapan"].isoformat()
                if inn2.get("tanggal_penerapan")
                else None
            ),
        },
        "skor_kecocokan": score,
        "hasil_ai": ai_result,
        "used_fallback": used_fallback,
    }
