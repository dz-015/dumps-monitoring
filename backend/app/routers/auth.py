import secrets
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.config import settings
from app.db.database import get_db
from app.db.models import Organization, User
from app.schemas import LoginRequest, Token, UserCreate, UserOut, UserUpdate

ALLOWED_AVATAR_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(400, "Email already registered")

    has_name = bool(data.organization_name)
    has_code = bool(data.join_code)
    if has_name == has_code:
        raise HTTPException(400, "Provide exactly one of organization_name or join_code")

    if has_name:
        org = Organization(name=data.organization_name, join_code=secrets.token_urlsafe(8))
        db.add(org)
        db.flush()
    else:
        org = db.query(Organization).filter(Organization.join_code == data.join_code).first()
        if not org:
            raise HTTPException(400, "Unknown join_code")

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        organization_id=org.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(401, "Неверный email или пароль")
    if not user.is_active:
        raise HTTPException(403, "Аккаунт деактивирован")
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
def update_me(
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(current_user, k, v)
    db.commit()
    db.refresh(current_user)
    return current_user


_SAFE_AVATAR_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}


@router.post("/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(400, f"Allowed image types: {sorted(ALLOWED_AVATAR_TYPES)}")

    # Read in chunks and abort as soon as the limit is crossed — a single
    # `await file.read()` would buffer an arbitrarily large body in RAM
    # before the size check ever ran.
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(64 * 1024):
        size += len(chunk)
        if size > settings.MAX_UPLOAD_BYTES:
            raise HTTPException(
                413, f"File too large (limit {settings.MAX_UPLOAD_BYTES} bytes)"
            )
        chunks.append(chunk)
    body = b"".join(chunks)

    # Trust the extension only after sanitising it — Path() strips directory
    # parts and we whitelist the ones we expect from the allowed image types.
    ext = Path(file.filename or "").suffix.lower()
    if ext not in _SAFE_AVATAR_EXTS:
        ext = ".bin"

    avatars_dir = Path(settings.UPLOAD_DIR) / "avatars"
    avatars_dir.mkdir(parents=True, exist_ok=True)

    # Drop the previous avatar so old uploads don't accumulate forever.
    if current_user.avatar_path:
        old = Path(settings.UPLOAD_DIR) / current_user.avatar_path
        old.unlink(missing_ok=True)

    dest_name = f"{current_user.id}_{uuid.uuid4().hex}{ext}"
    dest_path = avatars_dir / dest_name
    dest_path.write_bytes(body)

    current_user.avatar_path = f"avatars/{dest_name}"
    db.commit()
    db.refresh(current_user)
    return current_user
