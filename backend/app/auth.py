import hashlib
import secrets
import time

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.config import JWT_SECRET
from app.db import get_conn

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer()


def new_salt() -> str:
    return secrets.token_hex(16)


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()


def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": int(time.time()) + 8 * 3600}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def get_current_user(cred: HTTPAuthorizationCredentials = Depends(bearer)) -> str:
    try:
        payload = jwt.decode(cred.credentials, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")
    return payload["sub"]


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginRequest) -> dict:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (body.username,)).fetchone()
    if not row or not secrets.compare_digest(row["password_hash"], hash_password(body.password, row["salt"])):
        raise HTTPException(status_code=401, detail="Sai tài khoản hoặc mật khẩu")
    return {"token": create_token(row["id"])}
