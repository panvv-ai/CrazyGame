from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.panwatch.api import get_session
from src.panwatch.models import User

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=200)


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    password_salt = salt or os.urandom(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=password_salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return f"{password_salt.hex()}:{digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":", 1)
    except ValueError:
        return False
    candidate = hash_password(password, salt=bytes.fromhex(salt_hex))
    return hmac.compare_digest(candidate, f"{salt_hex}:{digest_hex}")


def create_token(username: str, secret_key: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": username,
            "iat": now,
            "exp": now + timedelta(days=30),
        },
        secret_key,
        algorithm="HS256",
    )


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db=Depends(get_session),
):
    if not request.app.state.config.enable_auth:
        return {"username": "local"}
    if credentials is None:
        raise HTTPException(401, "authentication required")
    try:
        payload = jwt.decode(
            credentials.credentials,
            request.app.state.config.secret_key,
            algorithms=["HS256"],
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(401, "invalid token") from exc
    user = db.scalar(select(User).where(User.username == payload.get("sub")))
    if user is None:
        raise HTTPException(401, "user not found")
    return {"username": user.username}


@router.get("/status")
def auth_status(db=Depends(get_session)):
    return {"initialized": db.scalar(select(User.id).limit(1)) is not None}


@router.post("/setup", status_code=201)
def setup(payload: Credentials, request: Request, db=Depends(get_session)):
    if db.scalar(select(User.id).limit(1)) is not None:
        raise HTTPException(409, "already initialized")
    db.add(User(username=payload.username, password_hash=hash_password(payload.password)))
    db.commit()
    return {"token": create_token(payload.username, request.app.state.config.secret_key)}


@router.post("/login")
def login(payload: Credentials, request: Request, db=Depends(get_session)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "invalid credentials")
    return {"token": create_token(payload.username, request.app.state.config.secret_key)}

