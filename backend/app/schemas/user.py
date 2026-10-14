from pydantic import BaseModel, EmailStr, field_validator
from typing import List
import re

from app.core.security import MAX_PASSWORD_BYTES


def normalize_email(value: str) -> str:
    """
    Canonical form used for storage and lookup.

    EmailStr lowercases only the domain, so `Alice@x.com` and `alice@x.com`
    used to register as two accounts, and Google sign-in (which lowercases)
    missed the first one and created a duplicate.
    """
    return str(value).strip().lower()


class UserCreate(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email", mode="after")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return normalize_email(v)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        # bcrypt ignores everything past 72 bytes; reject rather than let the
        # tail of a long passphrase silently not count.
        if len(v.encode("utf-8")) > MAX_PASSWORD_BYTES:
            raise ValueError(f"Password must be at most {MAX_PASSWORD_BYTES} bytes")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v

class UserRead(BaseModel):
    id: int
    email: EmailStr
    skills: List[str]

class UserUpdate(BaseModel):
    skills: List[str]

class Token(BaseModel):
    access_token: str
    token_type: str