import asyncio
import pandas as pd
import numpy as np
from itertools import combinations
from sentence_transformers import SentenceTransformer
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics import silhouette_score
from sklearn.metrics.pairwise import cosine_similarity
from app.database import database
from datetime import datetime
from typing import List, Dict

# ===============================
# MODEL
# Upgrade ke mpnet — lebih akurat untuk teks panjang (deskripsi),
# masih cukup ringan untuk server produksi.
# ===============================
embedding_model = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")

# ===============================
# CACHE (IN-MEMORY)
# ===============================
_cluster_insight_cache: List[Dict] = []
_cluster_last_run: datetime | None = None

BULK_INSERT_BATCH = 500
STATEMENT_TIMEOUT_MS = 300_000  # 5 menit


def set_cluster_cache(data: List[Dict]):
    global _cluster_insight_cache, _cluster_last_run
    _cluster_insight_cache = data
    _cluster_last_run = datetime.utcnow()


def get_cluster_cache():
    return _cluster_insight_cache, _cluster_last_run


# ===============================
# AUTO-SELECT K OPTIMAL (SILHOUETTE)
# ===============================
def find_optimal_k(embeddings: np.ndarray, k_min: int = 2, k_max: int = 10) -> int:
    n = len(embeddings)
    k_max_safe = min(k_max, n // 2)

    if k_max_safe < k_min:
        return k_min

    best_k = k_min
    best_score = -1.0

    for k in range(k_min, k_max_safe + 1):
        labels = AgglomerativeClustering(n_clusters=k).fit_predict(embeddings)
        try:
            score = silhouette_score(embeddings, labels, metric="cosine")
        except ValueError:
            continue

        print(f"   k={k} → silhouette={score:.4f}")

        if score > best_score:
            best_score = score
            best_k = k

    print(f"✅ Optimal k={best_k} (silhouette={best_score:.4f})")
    return best_k


# ===============================
# AUTO-LOAD CACHE FROM DATABASE
# ===============================
async def load_cache_from_database():
    """Load clustering results dari database dan rebuild cache. Dipanggil saat startup."""
    try:
        print("📄 Loading clustering cache from database...")

        last_run_row = await database.fetch_one(
            "SELECT MAX(processed_at) as last_run FROM clustering_result"
        )

        if not last_run_row or not last_run_row["last_run"]:
            print("⚠️ No clustering results found in database")
            return

        clusters_data = await database.fetch_all(
            """
            SELECT DISTINCT cluster_id
            FROM clustering_result
            ORDER BY cluster_id
            """
        )

        if not clusters_data:
            print("⚠️ No clusters found in database")
            return

        # Ambil top pair per cluster sekaligus + deskripsi
        top_pairs_raw = await database.fetch_all(
            """
            SELECT DISTINCT ON (s.cluster_id)
                s.cluster_id,
                s.inovasi_id_1,
                s.inovasi_id_2,
                s.similarity,
                a.judul_inovasi   AS judul_1,
                a.urusan_utama    AS urusan_1,
                a.tahapan_inovasi AS tahap_1,
                a.label_kematangan AS kematangan_1,
                a.admin_opd       AS opd_1,
                a.deskripsi       AS deskripsi_1,
                a.tanggal_penerapan AS tanggal_penerapan_1,
                b.judul_inovasi   AS judul_2,
                b.urusan_utama    AS urusan_2,
                b.tahapan_inovasi AS tahap_2,
                b.label_kematangan AS kematangan_2,
                b.admin_opd       AS opd_2,
                b.deskripsi       AS deskripsi_2,
                b.tanggal_penerapan AS tanggal_penerapan_2
            FROM similarity_result s
            JOIN data_inovasi a ON a.id = s.inovasi_id_1
            JOIN data_inovasi b ON b.id = s.inovasi_id_2
            ORDER BY s.cluster_id, s.similarity DESC
            """
        )

        counts_raw = await database.fetch_all(
            """
            SELECT cluster_id, COUNT(*) AS cnt
            FROM clustering_result
            GROUP BY cluster_id
            """
        )

        top_pairs_map = {row["cluster_id"]: dict(row) for row in top_pairs_raw}
        counts_map = {row["cluster_id"]: row["cnt"] for row in counts_raw}

        insights = []
        for cluster_row in clusters_data:
            cluster_id = cluster_row["cluster_id"]
            top_pair = top_pairs_map.get(cluster_id)
            if not top_pair:
                continue

            insights.append(
                {
                    "cluster_id": cluster_id,
                    "skor_kolaborasi": round(top_pair["similarity"], 4),
                    "jumlah_inovasi": counts_map.get(cluster_id, 0),
                    "inovasi_1": {
                        "id": top_pair["inovasi_id_1"],
                        "judul": top_pair["judul_1"],
                        "urusan": top_pair["urusan_1"],
                        "tahap": top_pair["tahap_1"],
                        "kematangan": top_pair["kematangan_1"],
                        "opd": top_pair["opd_1"],
                        "deskripsi": top_pair["deskripsi_1"] or "",
                        "tanggal_penerapan": (
                            top_pair["tanggal_penerapan_1"].isoformat()
                            if top_pair.get("tanggal_penerapan_1")
                            else None
                        ),
                    },
                    "inovasi_2": {
                        "id": top_pair["inovasi_id_2"],
                        "judul": top_pair["judul_2"],
                        "urusan": top_pair["urusan_2"],
                        "tahap": top_pair["tahap_2"],
                        "kematangan": top_pair["kematangan_2"],
                        "opd": top_pair["opd_2"],
                        "deskripsi": top_pair["deskripsi_2"] or "",
                        "tanggal_penerapan": (
                            top_pair["tanggal_penerapan_2"].isoformat()
                            if top_pair.get("tanggal_penerapan_2")
                            else None
                        ),
                    },
                }
            )

        insights = sorted(insights, key=lambda x: x["skor_kolaborasi"], reverse=True)

        global _cluster_insight_cache, _cluster_last_run
        _cluster_insight_cache = insights
        _cluster_last_run = last_run_row["last_run"]

        print(f"✅ Cache loaded: {len(insights)} clusters from {_cluster_last_run}")

    except Exception as e:
        print(f"❌ Error loading cache from database: {e}")
        import traceback

        traceback.print_exc()


# ===============================
# AUTO-DETECT NEW DATA & TRIGGER CLUSTERING
# ===============================
async def check_and_auto_run_clustering(threshold: int = 50):
    try:
        print(f"🔍 Checking for new data (threshold: {threshold})...")

        new_ids_rows = await database.fetch_all(
            """
            SELECT d.id
            FROM data_inovasi d
            WHERE d.judul_inovasi IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM clustering_result c WHERE c.id_inovasi = d.id
              )
            """
        )

        new_data_count = len(new_ids_rows)

        total_data = await database.fetch_val(
            "SELECT COUNT(*) FROM data_inovasi WHERE judul_inovasi IS NOT NULL"
        )
        clustered_data = await database.fetch_val(
            "SELECT COUNT(*) FROM clustering_result"
        )

        print(
            f"📊 Total: {total_data}, Clustered: {clustered_data}, "
            f"New (belum di-cluster): {new_data_count}"
        )

        if new_data_count >= threshold:
            print(f"🚀 AUTO-TRIGGERING clustering ({new_data_count} new data)")
            result = await run_clustering_pipeline()
            print(f"✅ Auto-clustering completed: {result}")
            return True
        else:
            print(f"✅ No need to re-cluster ({new_data_count} < {threshold})")
            return False

    except Exception as e:
        print(f"❌ Error in auto-check clustering: {e}")
        import traceback

        traceback.print_exc()
        return False


# ===============================
# LOAD DATA (BATCHED)
# Ambil deskripsi sebagai fitur utama clustering
# ===============================
async def load_data_inovasi(batch_size=100, offset=0) -> pd.DataFrame:
    rows = await database.fetch_all(
        """
        SELECT
            id,
            judul_inovasi,
            urusan_utama,
            deskripsi,
            tahapan_inovasi,
            label_kematangan,
            admin_opd,
            tanggal_penerapan
        FROM data_inovasi
        WHERE judul_inovasi IS NOT NULL
        ORDER BY id
        LIMIT :limit OFFSET :offset
        """,
        {"limit": batch_size, "offset": offset},
    )

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame([dict(r) for r in rows])


# ===============================
# EMBEDDING
# Fitur: judul + urusan (konteks bidang) + deskripsi (konten utama)
# Deskripsi mendapat bobot dominan karena teks lebih panjang.
# ===============================
def build_embeddings(df: pd.DataFrame) -> np.ndarray:
    # Fitur tunggal: hanya deskripsi.
    # Fallback ke judul_inovasi jika deskripsi kosong/null.
    def get_teks(row):
        desc = (row["deskripsi"] or "").strip()
        return desc if desc else (row["judul_inovasi"] or "").strip()

    df["teks_fitur"] = df.apply(get_teks, axis=1)

    return embedding_model.encode(
        df["teks_fitur"].tolist(),
        show_progress_bar=False,
        batch_size=16,
    )


# ===============================
# BULK INSERT HELPERS
# ===============================
async def _bulk_insert_clustering(records: list, now: datetime, model_name: str):
    for i in range(0, len(records), BULK_INSERT_BATCH):
        batch = records[i : i + BULK_INSERT_BATCH]
        placeholders = []
        params: dict = {}
        for idx, rec in enumerate(batch):
            placeholders.append(
                f"(:id_{idx}, :cluster_{idx}, :model_{idx}, :version_{idx}, :ts_{idx})"
            )
            params[f"id_{idx}"] = rec["id"]
            params[f"cluster_{idx}"] = rec["cluster"]
            params[f"model_{idx}"] = model_name
            params[f"version_{idx}"] = "v3"
            params[f"ts_{idx}"] = now

        await database.execute(
            f"""
            INSERT INTO clustering_result
                (id_inovasi, cluster_id, model_name, model_version, processed_at)
            VALUES {', '.join(placeholders)}
            """,
            params,
        )


async def _bulk_insert_similarity(records: list, now: datetime):
    for i in range(0, len(records), BULK_INSERT_BATCH):
        batch = records[i : i + BULK_INSERT_BATCH]
        placeholders = []
        params: dict = {}
        for idx, rec in enumerate(batch):
            placeholders.append(
                f"(:cluster_{idx}, :a_{idx}, :b_{idx}, :s_{idx}, :ts_{idx})"
            )
            params[f"cluster_{idx}"] = rec["cluster"]
            params[f"a_{idx}"] = rec["a"]
            params[f"b_{idx}"] = rec["b"]
            params[f"s_{idx}"] = rec["s"]
            params[f"ts_{idx}"] = now

        await database.execute(
            f"""
            INSERT INTO similarity_result
                (cluster_id, inovasi_id_1, inovasi_id_2, similarity, processed_at)
            VALUES {', '.join(placeholders)}
            """,
            params,
        )


# ===============================
# SAVE RESULTS
# ===============================
async def save_results_transactional(df, labels, embeddings, model_name):
    sim_matrix = cosine_similarity(embeddings)
    now = datetime.utcnow()

    cluster_records = [
        {"id": int(df.at[i, "id"]), "cluster": int(labels[i])} for i in range(len(df))
    ]

    similarity_records = []
    for i in range(len(df)):
        for j in range(i + 1, len(df)):
            if labels[i] != labels[j]:
                continue
            similarity = float(sim_matrix[i, j])
            if similarity < 0.5:
                continue
            similarity_records.append(
                {
                    "cluster": int(labels[i]),
                    "a": int(df.at[i, "id"]),
                    "b": int(df.at[j, "id"]),
                    "s": similarity,
                }
            )

    print(
        f"💾 Menyimpan {len(cluster_records)} cluster records "
        f"dan {len(similarity_records)} similarity pairs..."
    )

    await database.execute(f"SET statement_timeout = '{STATEMENT_TIMEOUT_MS}'")

    async with database.transaction():
        await database.execute("TRUNCATE TABLE similarity_result")
        await database.execute("TRUNCATE TABLE clustering_result")

    print("🗑️  Tabel lama berhasil dibersihkan.")

    try:
        await _bulk_insert_clustering(cluster_records, now, model_name)
        print(f"✅ clustering_result: {len(cluster_records)} baris tersimpan.")
    except Exception as e:
        print(f"❌ Gagal insert clustering_result: {e}")
        raise

    if similarity_records:
        try:
            await _bulk_insert_similarity(similarity_records, now)
            print(f"✅ similarity_result: {len(similarity_records)} baris tersimpan.")
        except Exception as e:
            print(f"❌ Gagal insert similarity_result: {e}")
            raise

    return len(similarity_records)


# ===============================
# HITUNG INSIGHT PER CLUSTER
# Sertakan deskripsi di setiap inovasi
# ===============================
def calculate_cluster_insights(df, embeddings, labels) -> List[Dict]:
    sim_matrix = cosine_similarity(embeddings)
    results = []

    for cluster_id in sorted(set(labels)):
        idxs = [i for i, lbl in enumerate(labels) if lbl == cluster_id]
        if len(idxs) < 2:
            continue

        best_score = 0.0
        best_pair = None

        for i, j in combinations(idxs, 2):
            score = float(sim_matrix[i, j])
            if score > best_score:
                best_score = score
                best_pair = (i, j)

        if not best_pair:
            continue

        a, b = best_pair

        results.append(
            {
                "cluster_id": int(cluster_id),
                "skor_kolaborasi": round(best_score, 4),
                "jumlah_inovasi": len(idxs),
                "inovasi_1": {
                    "id": int(df.at[a, "id"]),
                    "judul": df.at[a, "judul_inovasi"],
                    "urusan": df.at[a, "urusan_utama"],
                    "tahap": df.at[a, "tahapan_inovasi"],
                    "kematangan": df.at[a, "label_kematangan"],
                    "opd": df.at[a, "admin_opd"],
                    "deskripsi": (
                        df.at[a, "deskripsi"] if pd.notna(df.at[a, "deskripsi"]) else ""
                    ),
                    "tanggal_penerapan": (
                        df.at[a, "tanggal_penerapan"].isoformat()
                        if pd.notna(df.at[a, "tanggal_penerapan"])
                        else None
                    ),
                },
                "inovasi_2": {
                    "id": int(df.at[b, "id"]),
                    "judul": df.at[b, "judul_inovasi"],
                    "urusan": df.at[b, "urusan_utama"],
                    "tahap": df.at[b, "tahapan_inovasi"],
                    "kematangan": df.at[b, "label_kematangan"],
                    "opd": df.at[b, "admin_opd"],
                    "deskripsi": (
                        df.at[b, "deskripsi"] if pd.notna(df.at[b, "deskripsi"]) else ""
                    ),
                    "tanggal_penerapan": (
                        df.at[b, "tanggal_penerapan"].isoformat()
                        if pd.notna(df.at[b, "tanggal_penerapan"])
                        else None
                    ),
                },
            }
        )

    return sorted(results, key=lambda x: x["skor_kolaborasi"], reverse=True)


# ===============================
# MAIN PIPELINE
# ===============================
async def run_clustering_pipeline():
    all_df = []
    all_embeddings = []

    offset = 0
    batch_size = 100

    while True:
        df_batch = await load_data_inovasi(batch_size, offset)
        if df_batch.empty:
            break

        emb_batch = build_embeddings(df_batch)
        all_df.append(df_batch)
        all_embeddings.append(emb_batch)
        offset += batch_size

    if not all_df:
        set_cluster_cache([])
        return {"status": "skipped", "reason": "Data inovasi kosong"}

    df = pd.concat(all_df, ignore_index=True)
    embeddings = np.vstack(all_embeddings)

    if len(df) < 4:
        set_cluster_cache([])
        return {"status": "skipped", "reason": "Data tidak cukup untuk clustering"}

    print("🔎 Mencari k optimal via silhouette score...")
    optimal_k = find_optimal_k(embeddings, k_min=2, k_max=15)

    print(f"🔍 Clustering {len(df)} items dengan k={optimal_k}")
    print(f"📌 Fitur: deskripsi (fallback: judul_inovasi jika kosong)")
    print(f"🤖 Model: paraphrase-multilingual-mpnet-base-v2")

    model = AgglomerativeClustering(n_clusters=optimal_k)
    labels = model.fit_predict(embeddings)

    model_name = f"Agglomerative_mpnet_k={optimal_k}"

    total_pairs = await save_results_transactional(df, labels, embeddings, model_name)

    insights = calculate_cluster_insights(df, embeddings, labels)

    print(
        f"✅ Generated {len(insights)} cluster insights, {total_pairs} similarity pairs"
    )
    if insights:
        top = insights[0]
        print(f"✅ Top cluster {top['cluster_id']} | skor={top['skor_kolaborasi']}")
        print(
            f"   - {top['inovasi_1']['judul']} (OPD: {top['inovasi_1'].get('opd', 'N/A')})"
        )
        print(
            f"   - {top['inovasi_2']['judul']} (OPD: {top['inovasi_2'].get('opd', 'N/A')})"
        )
    else:
        print("⚠️ WARNING: Tidak ada insight yang dihasilkan!")

    set_cluster_cache(insights)
    print(f"✅ Cache diperbarui dengan {len(insights)} cluster")

    return {
        "status": "ok",
        "total_data": len(df),
        "clusters": optimal_k,
        "model": model_name,
        "fitur_clustering": ["deskripsi"],
        "total_insight": len(insights),
        "total_similarity_pairs": total_pairs,
        "top_3": insights[:3],
    }
