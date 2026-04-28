import json
import os

INPUT_FILE = "gadm41_IDN_2.json"
OUTPUT_FILE = "jatim_kab.geojson"


def filter_jawa_timur():
    print(f"📂 Membaca file: {INPUT_FILE} ...")

    if not os.path.exists(INPUT_FILE):
        print(f"❌ File '{INPUT_FILE}' tidak ditemukan!")
        print("   Pastikan file GADM sudah ada di folder yang sama dengan script ini.")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_features = len(data.get("features", []))
    print(f"   Total fitur Indonesia: {total_features}")

    jatim_features = [
        feature
        for feature in data["features"]
        if feature.get("properties", {}).get("NAME_1") == "JawaTimur"
    ]

    if not jatim_features:
        print("❌ Tidak ada data Jawa Timur ditemukan!")
        all_names = sorted(
            set(f["properties"].get("NAME_1", "") for f in data["features"])
        )
        print("   Semua NAME_1 yang ada:", all_names)
        return

    # Buat GeoJSON baru hanya Jawa Timur
    jatim_geojson = {"type": "FeatureCollection", "features": jatim_features}

    # Simpan output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(jatim_geojson, f, ensure_ascii=False)

    print(f"\n✅ Berhasil!")
    print(f"   Total kabupaten/kota Jawa Timur: {len(jatim_features)}")
    print(f"   (Seharusnya 38: 29 Kabupaten + 9 Kota)")
    print(f"\n📄 File output: {OUTPUT_FILE}")

    # Print daftar nama untuk verifikasi matching dengan data pemda
    print("\n📋 Daftar NAME_2 (untuk verifikasi nama vs data pemda kamu):")
    for feat in sorted(jatim_features, key=lambda x: x["properties"].get("NAME_2", "")):
        name2 = feat["properties"].get("NAME_2", "?")
        name_type = feat["properties"].get("ENGTYPE_2", "")
        print(f"   - {name2}  [{name_type}]")

    print(f"\n➡️  Sekarang salin '{OUTPUT_FILE}' ke folder: frontend/public/")


if __name__ == "__main__":
    filter_jawa_timur()