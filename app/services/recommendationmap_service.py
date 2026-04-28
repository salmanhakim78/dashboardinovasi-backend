"""
Recommendation Service: SIAPIN BRIDA Jatim
Optimized for 50km proximity, smart reasoning, and 5 recs PER innovation.
"""
from typing import List, Tuple, Dict
from math import radians, cos, sin, asin, sqrt
from collections import defaultdict

class RecommendationService:
    def __init__(self):
        # Sesuai permintaan: Batas keras kolaborasi spasial adalah 50 KM
        self.max_distance_km = 50 

    def haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Menghitung jarak antara dua titik koordinat (km)"""
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        return c * 6371

    def generate_recommendations(
        self,
        innovations_data: List[dict],
        similar_pairs: List[Tuple[int, int, float]],
        top_n: int = 5
    ) -> List[dict]:
        
        # Keranjang pelacak: memastikan 1 inovasi sumber maksimal dapat top_n (5) pasangan
        recs_per_innovation: Dict[int, List[dict]] = defaultdict(list)
        all_recommendations = []
        
        # Sortir similar_pairs berdasarkan similarity tertinggi dulu
        sorted_pairs = sorted(similar_pairs, key=lambda x: x[2], reverse=True)
        
        for idx1, idx2, similarity in sorted_pairs: 
            try:
                inv1 = innovations_data[idx1]
                inv2 = innovations_data[idx2]
                
                if not all(k in inv1 and k in inv2 for k in ['lat', 'lon']):
                    continue

                source_id = inv1['no']
                target_id = inv2['no']

                # CEK LIMIT: Jika inovasi ini sudah punya 5 pasangan, skip dan cari inovasi lain
                if len(recs_per_innovation[source_id]) >= top_n:
                    continue

                dist = self.haversine_distance(
                    float(inv1['lat']), float(inv1['lon']),
                    float(inv2['lat']), float(inv2['lon'])
                )
                
                # Jika jarak lurus lebih dari 50km, skip
                if dist > self.max_distance_km:
                    continue
                
                # Generate alasan TANPA kalimat jarak (diserahkan ke OSRM)
                reason = self._generate_collaboration_reason(inv1, inv2, similarity)
                
                rec_data = {
                    'inovasi_1_id': source_id,
                    'inovasi_1_judul': inv1['judul_inovasi'],
                    'inovasi_2_id': target_id,
                    'inovasi_2_judul': inv2['judul_inovasi'],
                    'similarity_score': round(similarity, 3),
                    'distance_km': round(dist, 2), # Disimpan sbg data, bukan teks alasan
                    'is_feasible': True,  
                    'collaboration_reason': reason
                }
                
                # Masukkan ke keranjang pelacak dan list utama
                recs_per_innovation[source_id].append(rec_data)
                all_recommendations.append(rec_data)
                    
            except (IndexError, KeyError, TypeError):
                continue
        
        return all_recommendations

    def _generate_collaboration_reason(self, inv1: dict, inv2: dict, sim: float) -> str:
        """
        Alasan kolaborasi — TIDAK menyebut jarak karena sudah ditampilkan
        oleh kotak analisis OSRM di frontend secara akurat.
        """
        urusan1 = str(inv1.get('urusan_utama') or "").lower()
        urusan2 = str(inv2.get('urusan_utama') or "").lower()
        
        full_text = f"{inv1.get('judul_inovasi')} {inv1.get('deskripsi')} {inv2.get('judul_inovasi')} {inv2.get('deskripsi')}".lower()
        
        # 1. Analisis Sektor
        if urusan1 == urusan2 and urusan1 != "":
            pembuka = f"Kedua inovasi berada di bawah sektor {urusan1.capitalize()}, memungkinkan standarisasi layanan dan pertukaran data."
        else:
            themes = self._detect_common_themes(full_text)
            tema_str = f" di bidang {', '.join(themes)}" if themes else ""
            pembuka = f"Terdapat irisan fungsi layanan{tema_str} yang saling melengkapi."

        # 2. Analisis Teknis
        digital_keywords = ['e-', 'sistem', 'digital', 'aplikasi', 'online', 'elektronik', 'website', 'android']
        is_digital = any(k in full_text for k in digital_keywords)
        metode = " Fokus pada integrasi sistem/modul." if is_digital else " Fokus pada pertukaran SOP dan tata kelola."

        return f"{pembuka}{metode}"

    def _detect_common_themes(self, text: str) -> List[str]:
        theme_keywords = {
            'pendidikan': ['sekolah', 'belajar', 'siswa', 'guru', 'smk'],
            'kesehatan': ['rsud', 'pasien', 'medis', 'puskesmas', 'stunting'],
            'pertanian': ['petani', 'panen', 'pangan', 'irigasi'],
            'ekonomi': ['umkm', 'usaha', 'pasar', 'bisnis'],
            'lingkungan': ['sampah', 'daur ulang', 'kebersihan']
        }
        return [t for t, keywords in theme_keywords.items() if any(k in text for k in keywords)]

    def rank_by_impact_potential(self, recommendations: List[dict], innovations_data: List[dict]) -> List[dict]:
        lookup = {i['no']: i for i in innovations_data}
        for rec in recommendations:
            mat1 = lookup.get(rec['inovasi_1_id'], {}).get('kematangan', 50)
            mat2 = lookup.get(rec['inovasi_2_id'], {}).get('kematangan', 50)
            rec['impact_score'] = (rec['similarity_score'] * 0.7) + (((mat1 + mat2) / 2) / 100 * 0.3)
        
        recommendations.sort(key=lambda x: x.get('impact_score', 0), reverse=True)
        return recommendations

recommendationmap_service = RecommendationService()