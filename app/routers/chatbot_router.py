from fastapi import APIRouter
from app.schemas import ChatRequest
from app.services.chatbot_service import chatbot_answer

router = APIRouter(prefix="/api", tags=["Chatbot"])


@router.post("/chatbot")
async def chatbot(req: ChatRequest):
    answer = await chatbot_answer(req.question)

    return {
        "question": req.question,
        "answer": answer,
    }
