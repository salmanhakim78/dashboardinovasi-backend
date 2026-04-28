import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

MODEL_NAME = "models/gemini-2.5-flash-lite"


def call_gemini(prompt: str, mode: str) -> str:
    if mode == "insight":
        api_key = os.getenv("GEMINI_INSIGHT_API_KEY")
    elif mode == "recommendation":
        api_key = os.getenv("TOP_REKOMENDASI_API_KEY")
    elif mode == "collaboration":
        api_key = os.getenv("GEMINI_COLLAB_API_KEY")
    elif mode == "chatbot":
        api_key = os.getenv("GEMINI_CHATBOT_API_KEY")
    else:
        raise ValueError("Mode Gemini tidak dikenali")

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content(prompt)

    return response.text
