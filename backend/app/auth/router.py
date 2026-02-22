from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session, select
from app.database import get_session
from app.auth.models import User, UserCreate, UserLogin, UserRead, Token
from app.auth.utils import hash_password, verify_password, create_access_token, get_current_user
from app.config import settings
from app.limiter import limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

_COOKIE_NAME = "access_token"
_COOKIE_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


@router.post("/register", response_model=UserRead, status_code=201)
@limiter.limit("10/minute")
def register(request: Request, user_in: UserCreate, session: Session = Depends(get_session)):
    existing = session.exec(select(User).where(User.username == user_in.username)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already taken")
    existing_email = session.exec(select(User).where(User.email == user_in.email)).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=hash_password(user_in.password),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("10/minute")
def login(
    request: Request,
    credentials: UserLogin,
    response: Response,
    session: Session = Depends(get_session),
):
    user = session.exec(select(User).where(User.username == credentials.username)).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    token = create_access_token({"sub": user.username})

    # Set httpOnly cookie — JS cannot read this, prevents XSS token theft
    response.set_cookie(
        key=_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/",
    )

    return Token(
        access_token=token,  # still returned for non-browser API clients
        user=UserRead(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(key=_COOKIE_NAME, path="/")


@router.get("/profile", response_model=UserRead)
def profile(current_user: User = Depends(get_current_user)):
    return current_user
