from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User
from hashing import verify_password
from jwt_handler import create_access_token
from oauth2 import get_current_active_user
import schemas

router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)


def authenticate_user(username: str, password: str, db: Session):
    """Authenticate user by username and password"""
    user = db.query(User).filter(User.username == username).first()

    if not user:
        return False

    if not verify_password(password, user.hashed_password):
        return False

    if not user.is_active:
        return False

    return user


@router.post("/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """Login endpoint"""
    user = authenticate_user(
        username=user_credentials.username,
        password=user_credentials.password,
        db=db
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username
    }
