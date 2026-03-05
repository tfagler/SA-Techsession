import asyncio
from sqlalchemy import select
from app.database import SessionLocal
from app.models import User
from app.security import hash_password


async def seed_admin(email: str, password: str) -> None:
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            print('Admin already exists')
            return
        user = User(email=email, password_hash=hash_password(password), cheap_mode=False, daily_hosted_token_budget=50000)
        db.add(user)
        await db.commit()
        print('Admin created')


if __name__ == '__main__':
    import os

    email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
    password = os.getenv('ADMIN_PASSWORD', 'admin12345')
    asyncio.run(seed_admin(email, password))
