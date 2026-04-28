import requests

N8N_WEBHOOK_URL = "http://localhost:5678/webhook/chat"


def send_to_n8n(question: str):
    payload = {"question": question}

    response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=120)

    print("Status:", response.status_code)
    print("Text:", response.text)

    if not response.text.strip():
        return {"answer": "n8n tidak mengembalikan respon"}

    try:
        return response.json()
    except Exception:
        return {"answer": "Response n8n bukan JSON"}
