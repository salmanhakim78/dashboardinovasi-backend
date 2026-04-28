def calculate_collaboration_score(inn1: dict, inn2: dict) -> int:
    """
    Menghitung skor kecocokan kolaborasi dua inovasi
    menggunakan rule-based scoring (tanpa AI).
    """

    score = 0

    # 1. Jenis inovasi sama
    if inn1.get("jenis") and inn1.get("jenis") == inn2.get("jenis"):
        score += 25

    # 2. Urusan utama sama
    if inn1.get("urusan_utama") and inn1.get("urusan_utama") == inn2.get(
        "urusan_utama"
    ):
        score += 30

    # 3. Lintas OPD (nilai tambah kolaborasi)
    if inn1.get("admin_opd") and inn2.get("admin_opd"):
        if inn1.get("admin_opd") != inn2.get("admin_opd"):
            score += 15

    # 4. Tahapan inovasi sama
    if inn1.get("tahapan") and inn1.get("tahapan") == inn2.get("tahapan"):
        score += 15

    # Maksimal 100
    return min(score, 100)
