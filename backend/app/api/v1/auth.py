import uuid
import httpx
from datetime import timedelta
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.core.database import get_session
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.users import User

router = APIRouter()

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate,
    session: AsyncSession = Depends(get_session)
) -> Any:
    """
    Register a new user.
    """
    # Check if user already exists
    stmt = select(User).where(User.email == user_in.email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )
    
    # Create new user
    db_user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
    )
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    return db_user

@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session)
) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    # Find user by email (form_data.username is used for email)
    stmt = select(User).where(User.email == form_data.username)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Generate access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(
            user.id, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }

@router.get("/google/login")
async def google_login():
    """Redirects the client to Google's OAuth2 authorization endpoint."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google OAuth is not configured on this server."
        )
    redirect_uri = "http://localhost:8000/api/v1/auth/google/callback"
    scope = "openid email profile"
    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?response_type=code"
        f"&client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
    )
    return RedirectResponse(url)

@router.get("/google/callback")
async def google_callback(code: str, session: AsyncSession = Depends(get_session)):
    """Receives auth code from Google, verifies, upserts user, and redirects to Next.js."""
    redirect_uri = "http://localhost:8000/api/v1/auth/google/callback"
    
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri
            }
        )
        if token_res.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retrieve token from Google.")
        
        token_data = token_res.json()
        access_token = token_data.get("access_token")
        
        user_info_res = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if user_info_res.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retrieve user info from Google.")
        
        user_info = user_info_res.json()
        email = user_info.get("email")
        if not email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email not provided by Google.")
            
    stmt = select(User).where(User.email == email)
    db_res = await session.execute(stmt)
    user = db_res.scalar_one_or_none()
    
    if not user:
        user = User(
            email=email,
            hashed_password=get_password_hash(f"oauth_{uuid.uuid4().hex}"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    our_token = create_access_token(user.id, expires_delta=access_token_expires)
    
    # Redirect back to the frontend with token and email as query params
    frontend_url = f"http://localhost:3000/dashboard?token={our_token}&email={email}"
    return RedirectResponse(frontend_url)

@router.get("/github/login")
async def github_login():
    """Redirects the client to GitHub's OAuth2 authorization endpoint."""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub OAuth is not configured on this server."
        )
    redirect_uri = "http://localhost:8000/api/v1/auth/github/callback"
    scope = "user:email"
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
    )
    return RedirectResponse(url)

@router.get("/github/callback")
async def github_callback(code: str, session: AsyncSession = Depends(get_session)):
    """Receives auth code from GitHub, verifies, upserts user, and redirects to Next.js."""
    redirect_uri = "http://localhost:8000/api/v1/auth/github/callback"
    
    async with httpx.AsyncClient() as client:
        token_res = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri
            }
        )
        if token_res.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retrieve token from GitHub.")
        
        token_data = token_res.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Access token missing in GitHub response.")
        
        user_info_res = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}"}
        )
        if user_info_res.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retrieve user profile from GitHub.")
        
        user_info = user_info_res.json()
        email = user_info.get("email")
        
        if not email:
            email_res = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"token {access_token}"}
            )
            if email_res.status_code == 200:
                emails = email_res.json()
                primary_email = next((e for e in emails if e.get("primary")), None)
                if primary_email:
                    email = primary_email.get("email")
                    
        if not email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email not provided or accessible on GitHub account.")
            
    stmt = select(User).where(User.email == email)
    db_res = await session.execute(stmt)
    user = db_res.scalar_one_or_none()
    
    if not user:
        user = User(
            email=email,
            hashed_password=get_password_hash(f"oauth_{uuid.uuid4().hex}"),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    our_token = create_access_token(user.id, expires_delta=access_token_expires)
    
    frontend_url = f"http://localhost:3000/dashboard?token={our_token}&email={email}"
    return RedirectResponse(frontend_url)
