"""
NLP Service: Semantic similarity analysis using Sentence Transformers
Optimized for BRIDA SIAPIN Project
"""
from sentence_transformers import SentenceTransformer, util
import numpy as np
from typing import List, Tuple
import torch # Tambahkan ini untuk cek hardware acceleration

class NLPService:
    def __init__(self):
        """
        Initialize NLP model
        Using 'paraphrase-multilingual-MiniLM-L12-v2' for Indonesian support
        """
        # Cek apakah ada GPU (CUDA), kalau ada pakai GPU biar lebih ngebut
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2', device=self.device)
    
    def compute_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Convert text to embeddings (vector representation)
        """
        # Pembersihan teks yang lebih aman
        cleaned_texts = [str(text).strip() if text and str(text).strip() != "" else "Tidak ada deskripsi" for text in texts]
        
        # Optimasi: normalize_embeddings=True membuat perhitungan cosine similarity lebih akurat & cepat
        embeddings = self.model.encode(
            cleaned_texts, 
            convert_to_tensor=False, 
            show_progress_bar=False,
            normalize_embeddings=True 
        )
        return embeddings
    
    def find_similar_innovations(
        self, 
        embeddings: np.ndarray, 
        threshold: float = 0.45 # Sesuaikan default dengan yang ada di router (0.45)
    ) -> List[Tuple[int, int, float]]:
        """
        Find pairs of similar innovations based on semantic similarity
        """
        similar_pairs = []
        
        # Menghitung cosine similarity matrix secara masif (lebih cepat)
        cosine_scores = util.cos_sim(embeddings, embeddings)
        
        n = len(embeddings)
        # Gunakan list comprehension atau iterasi yang efisien
        for i in range(n):
            for j in range(i + 1, n):
                score = float(cosine_scores[i][j])
                if score >= threshold:
                    similar_pairs.append((i, j, score))
        
        # Sort by similarity score (descending)
        similar_pairs.sort(key=lambda x: x[2], reverse=True)
        
        return similar_pairs

# Singleton instance
nlp_service = NLPService()