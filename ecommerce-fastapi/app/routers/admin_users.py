from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_role
from app.models.user import User
from app.schemas.user import UserRead
from app.services.auth_service import hash_password

router = APIRouter(prefix="/admin/users", tags=["admin"], dependencies=[Depends(require_role("Admin"))])


@router.get("", response_model=list[UserRead])
async def list_users(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.id))
    return result.scalars().all()


@router.post("", response_model=UserRead, status_code=201)
async def create_user(body: dict, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == body.get("username")))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already taken")

    user = User(
        username=body["username"],
        email=body.get("email", ""),
        password=hash_password(body.get("password", "changeme")),
        role=body.get("role", "User"),
        is_active=body.get("is_active", True),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserRead)
async def update_user(user_id: int, body: dict, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if "username" in body:
        user.username = body["username"]
    if "email" in body:
        user.email = body["email"]
    if "role" in body:
        user.role = body["role"]
    if "is_active" in body:
        user.is_active = body["is_active"]
    if "password" in body:
        user.password = hash_password(body["password"])

    await db.commit()
    await db.refresh(user)
    return user
