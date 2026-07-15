from pydantic import BaseModel, EmailStr
from typing import List

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserRead(BaseModel):
    id: int
    email: EmailStr
    skills: List[str]

class UserUpdate(BaseModel):
    skills: List[str]

class Token(BaseModel):
    access_token: str
    token_type: str