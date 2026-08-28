from pydantic import BaseModel, EmailStr, field_validator
from typing import List
import re

class UserCreate(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
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