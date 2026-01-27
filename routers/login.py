from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from database import get_db
from models import User
from hashing import verify_password
from jwt_handler import create_access_token
from oauth2 import get_current_active_user
from logger import get_logger
import schemas

router = APIRouter(
    prefix="/auth",
    tags=["authentication"]
)

logger = get_logger()


def authenticate_user(username: str, password: str, db: Session):
    user = db.query(User).filter(User.username == username).first()

    if not user:
        return False

    if not verify_password(password, user.hashed_password):
        return False

    if not user.is_active:
        return False

    return user


@router.post("/login", response_model=schemas.Token)
def login(user_credentials: schemas.UserLogin, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    
    user = authenticate_user(
        username=user_credentials.username,
        password=user_credentials.password,
        db=db
    )

    if not user:
        logger.log_auth_event(
            event="LOGIN",
            user=user_credentials.username,
            success=False,
            client_ip=client_ip,
            details="Invalid credentials"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "username": user.username}
    )
    
    logger.log_auth_event(
        event="LOGIN",
        user=user.username,
        success=True,
        client_ip=client_ip
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": user.id,
        "username": user.username
    }
