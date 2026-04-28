from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
import jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/auth", tags=["Auth"])

ADMIN_USER = os.getenv("ADMIN_USER")
ADMIN_PASS = os.getenv("ADMIN_PASS")
JWT_SECRET = os.getenv("JWT_SECRET")


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(data: LoginRequest):
    """
    Login endpoint untuk admin
    Returns JWT token jika berhasil
    """
    if not ADMIN_USER or not ADMIN_PASS or not JWT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: environment variables not set",
        )

    if data.username != ADMIN_USER or data.password != ADMIN_PASS:
        raise HTTPException(status_code=401, detail="Username atau password salah")

    token = jwt.encode(
        {
            "role": "admin",
            "sub": data.username,
            "exp": datetime.now(timezone.utc) + timedelta(hours=2),
        },
        JWT_SECRET,
        algorithm="HS256",
    )

    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return {"token": token}
