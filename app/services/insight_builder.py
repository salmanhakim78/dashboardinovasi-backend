import json


def build_insight_prompt(stats, trend, top_opd, tahap_dist, top_urusan):
    """Build prompt for dashboard homepage AI insights."""
    return f"""
Kamu adalah analis data inovasi daerah Pemerintah Provinsi Jawa Timur.

Tugasmu adalah menyusun INSIGHT STRATEGIS untuk pimpinan daerah
berdasarkan DASHBOARD DATA INOVASI.

Buat 5 insight SINGKAT, TAJAM, dan BERORIENTASI KEBIJAKAN
dalam format JSON array berikut:

FORMAT OUTPUT:
[
  {{"icon":"📈","text":"...","type":"success"}},
  {{"icon":"🏆","text":"...","type":"success"}},
  {{"icon":"⚠️","text":"...","type":"warning"}},
  {{"icon":"💡","text":"...","type":"info"}},
  {{"icon":"🎯","text":"...","type":"success"}}
]

ATURAN KETAT:
- Output HARUS valid JSON (bisa langsung di-parse)
- Gunakan HANYA type berikut: success, warning, info
- Setiap insight MINIMAL 12 kata
- Jangan hanya menyebut angka, jelaskan maknanya
- Fokus pada pola, tren, dan perbandingan
- Jika ada risiko, tuliskan sebagai peringatan yang jelas
- Jika ada peluang, sertakan saran singkat yang kontekstual
- Bandingkan proporsi, tren, atau distribusi
- Jika ada stagnasi / penurunan, sebutkan RISIKONYA
- Jika ada peluang, sebutkan ARAH TINDAKAN singkat
- Hindari frasa normatif kosong (misal: "perlu ditingkatkan")
- JANGAN membuat asumsi di luar data yang diberikan
- Gunakan bahasa formal, ringkas, gaya eksekutif pemerintah

DATA UTAMA:
- Total inovasi: {stats['total_inovasi']}
- Inovasi digital: {stats['inovasi_digital']}
- Inovasi baru tahun ini: {stats['inovasi_tahun_ini']}
- Rata-rata kematangan inovasi: {stats['rata_kematangan']}

TREN INOVASI PER TAHUN:
{trend}

DISTRIBUSI TAHAPAN INOVASI:
{tahap_dist}

TOP 5 OPD PALING INOVATIF:
{top_opd}

TOP 5 URUSAN DENGAN INOVASI TERBANYAK:
{top_urusan}

Kembalikan HANYA JSON array sesuai format.
"""


def build_collaboration_prompt(data):
    """Build prompt for collaboration recommendation analysis (dari similarity_result)."""

    deskripsi_1 = data.get("deskripsi_1", "") or ""
    deskripsi_2 = data.get("deskripsi_2", "") or ""

    # Potong deskripsi agar prompt tidak terlalu panjang — 600 char agar AI punya konteks cukup
    deskripsi_1_short = (
        deskripsi_1[:600] + "..." if len(deskripsi_1) > 600 else deskripsi_1
    )
    deskripsi_2_short = (
        deskripsi_2[:600] + "..." if len(deskripsi_2) > 600 else deskripsi_2
    )

    return f"""
Kamu adalah analis kebijakan inovasi daerah Pemerintah Provinsi Jawa Timur.

Tugasmu adalah menyusun rekomendasi kolaborasi inovasi berbasis data
yang akan ditampilkan pada dashboard pimpinan daerah.

Buat 1 rekomendasi kolaborasi inovasi dalam format JSON berikut:

{{
  "judul_kolaborasi": "...",
  "opd_terlibat": ["...", "..."],
  "skor_kecocokan": {round(data['similarity'], 2)},
  "alasan_kesesuaian": "...",
  "manfaat": ["...", "...", "..."],
  "potensi_dampak": ["...", "...", "..."],
  "tingkat_rekomendasi": "Replikasi Lintas OPD / Kolaborasi Pengembangan / Referensi Praktik Baik"
}}

ATURAN PENULISAN:
- Bahasa formal, ringkas, gaya kebijakan publik
- Fokus pada MAKNA dan DAMPAK, bukan teknis
- Jangan mengarang data baru
- Manfaat dan dampak harus relevan dengan isi deskripsi inovasi
- Gunakan istilah pemerintahan Indonesia
- Maksimal 2 kalimat untuk alasan kesesuaian
- Minimal 3 poin manfaat (idealnya 3-5 poin yang BERBEDA dan SPESIFIK)
- Minimal 3 poin potensi dampak (idealnya 3-5 poin yang BERBEDA dan SPESIFIK)
- Setiap insight HARUS mengandung implikasi kebijakan bagi pimpinan daerah
- Gunakan sudut pandang pengambilan keputusan strategis

DATA INOVASI:
Inovasi 1: {data['inovasi_1']} ({data['opd_1']})
Urusan: {data.get('urusan', '-')}
Tahap: {data.get('tahap', '-')}
Deskripsi: {deskripsi_1_short if deskripsi_1_short else '(tidak tersedia)'}

Inovasi 2: {data['inovasi_2']} ({data['opd_2']})
Urusan: {data.get('urusan_2', data.get('urusan', '-'))}
Tahap: {data.get('tahap_2', data.get('tahap', '-'))}
Deskripsi: {deskripsi_2_short if deskripsi_2_short else '(tidak tersedia)'}

Skor kemiripan: {round(data['similarity'], 2)}

Kembalikan HANYA JSON tanpa teks tambahan.
"""


def build_input_collaboration_prompt(a, b, score):
    """Build prompt for user input collaboration (manual pilih 2 inovasi)."""

    deskripsi_a = (a.get("deskripsi") or "")[:600]
    deskripsi_b = (b.get("deskripsi") or "")[:600]
    if len(a.get("deskripsi") or "") > 600:
        deskripsi_a += "..."
    if len(b.get("deskripsi") or "") > 600:
        deskripsi_b += "..."

    return f"""
Kamu adalah analis inovasi sektor publik Indonesia.

INOVASI A
Judul       : {a['judul_inovasi']}
OPD         : {a['admin_opd']}
Urusan Utama: {a['urusan_utama']}
Jenis       : {a['jenis']}
Deskripsi   : {deskripsi_a if deskripsi_a else '(tidak tersedia)'}

INOVASI B
Judul       : {b['judul_inovasi']}
OPD         : {b['admin_opd']}
Urusan Utama: {b['urusan_utama']}
Jenis       : {b['jenis']}
Deskripsi   : {deskripsi_b if deskripsi_b else '(tidak tersedia)'}

Skor kecocokan awal sistem: {score}%

ATURAN PENILAIAN BERDASARKAN SKOR:
- <30 : kolaborasi eksploratif, risiko tinggi, manfaat terbatas
- 30–60: kolaborasi potensial, perlu pilot project
- >60 : kolaborasi kuat dan strategis

TUGAS:
1. Tentukan tingkat kolaborasi (Sangat Tinggi / Tinggi / Sedang / Rendah)
2. Buat judul kolaborasi inovasi
3. Jelaskan alasan sinergi berdasarkan isi deskripsi kedua inovasi
4. Jelaskan manfaat kolaborasi (minimal 3 poin, idealnya 3-5 poin)
5. Jelaskan potensi dampak pelayanan publik (minimal 3 poin, idealnya 3-5 poin)

WAJIB format JSON:
{{
  "judul_kolaborasi": "",
  "tingkat_kolaborasi": "",
  "alasan_sinergi": "",
  "manfaat_kolaborasi": ["...", "...", "...", "...", "..."],
  "potensi_dampak": ["...", "...", "...", "...", "..."]
}}

ATURAN:
- Bahasa formal kebijakan publik
- Maksimal 2 kalimat untuk alasan sinergi
- Alasan HARUS mencerminkan isi deskripsi, bukan hanya judul
- Manfaat dan dampak HARUS realistis sesuai skor
- Setiap poin manfaat dan dampak harus BERBEDA, SPESIFIK, tidak generik
- Jangan berlebihan jika skor rendah
- Output HARUS JSON VALID tanpa teks tambahan
"""
