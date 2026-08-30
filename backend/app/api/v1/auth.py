from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from jose import JWTError, jwt

from app.core.database import get_session
from app.core.security import verify_password, get_password_hash, create_access_token, ALGORITHM
from app.models.users import User
from app.schemas.user import UserCreate, UserRead, UserUpdate, Token
from app.config import settings

router = APIRouter()

# Tells FastAPI that this is where the frontend fetches the token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme), 
    session: AsyncSession = Depends(get_session)
) -> User:
    """Dependency to verify JWT token and fetch the user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    query = select(User).where(User.email == email)
    result = await session.execute(query)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    return user

@router.post("/register", response_model=UserRead)
async def register(user_in: UserCreate, session: AsyncSession = Depends(get_session)):
    # Check if email exists
    query = select(User).where(User.email == user_in.email)
    result = await session.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    # Create and save user
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        skills=[]
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session)
):
    # OAuth2PasswordRequestForm uses 'username' and 'password' fields. 
    # Our 'username' is the email.
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Login attempt for: '{form_data.username}'")
    
    query = select(User).where(User.email == form_data.username)
    result = await session.execute(query)
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning(f"Login failed: no user found with email '{form_data.username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    pwd_ok = verify_password(form_data.password, user.hashed_password)
    logger.info(f"Password verification for '{form_data.username}': {pwd_ok}, hash prefix: {user.hashed_password[:10]}...")
    
    if not pwd_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token = create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    """Fetch the currently logged in user."""
    return current_user

@router.put("/me/skills", response_model=UserRead)
async def update_skills(
    skills_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """Update the skills the user wants to be alerted for."""
    # Normalize skills to lowercase and remove blanks
    current_user.skills = [s.strip().lower() for s in skills_in.skills if s.strip()]
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return current_user