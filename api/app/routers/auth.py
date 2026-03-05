from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import User
from app.schemas import LoginIn, RegisterIn, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password
from app.deps import get_current_user


router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/register', response_model=TokenOut)
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Email already used')

    user = User(email=payload.email, password_hash=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(str(user.id))
    return TokenOut(access_token=token)


@router.post('/login', response_model=TokenOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid credentials')
    token = create_access_token(str(user.id))
    return TokenOut(access_token=token)


@router.get('/me', response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return UserOut(
        id=user.id,
        email=user.email,
        cheap_mode=user.cheap_mode,
        daily_hosted_token_budget=user.daily_hosted_token_budget,
    )
