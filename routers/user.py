from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from database import get_db
from models import User
from hashing import hash_password, verify_password
from oauth2 import require_admin_user, get_current_active_user
import schemas

router = APIRouter(
    prefix="/users",
    tags=["users"]
)


@router.post("/create", response_model=schemas.UserResponse)
def create_user(
        user_data: schemas.UserCreate,
        db: Session = Depends(get_db),
        admin_user: User = Depends(require_admin_user)
):
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered"
        )
    
    existing_email = db.query(User).filter(User.email == user_data.email).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )
    
    hashed_password = hash_password(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.put("/change-password")
def change_password(
        password_data: schemas.PasswordChange,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    current_user.hashed_password = hash_password(password_data.new_password)
    db.commit()

    return {"message": "Password changed successfully"}


@router.put("/admin/change-password/{user_id}")
def admin_change_password(
        user_id: int,
        password_data: schemas.AdminPasswordChange,
        db: Session = Depends(get_db),
        admin_user: User = Depends(require_admin_user)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    target_user.hashed_password = hash_password(password_data.new_password)
    db.commit()

    return {"message": f"Password changed for user {target_user.username}"}


@router.put("/admin/toggle-active/{user_id}")
def admin_toggle_user_active(
        user_id: int,
        db: Session = Depends(get_db),
        admin_user: User = Depends(require_admin_user)
):
    if user_id == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify admin user status"
        )
    
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    target_user.is_active = not target_user.is_active
    db.commit()
    
    status_str = "activated" if target_user.is_active else "deactivated"
    return {"message": f"User '{target_user.username}' has been {status_str}"}


@router.delete("/admin/delete/{user_id}")
def admin_delete_user(
        user_id: int,
        db: Session = Depends(get_db),
        admin_user: User = Depends(require_admin_user)
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    if target_user.id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    deleted_username = target_user.username
    
    db.delete(target_user)
    db.commit()
    
    return {"message": f"User '{deleted_username}' has been successfully deleted"}


@router.get("/me", response_model=schemas.UserResponse)
def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.get("/list", response_model=list[schemas.UserResponse])
def list_users(
        db: Session = Depends(get_db),
        admin_user: User = Depends(require_admin_user),
        skip: int = 0,
        limit: int = 100
):
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/{user_id}", response_model=schemas.UserResponse)
def get_user(
        user_id: int,
        db: Session = Depends(get_db),
        admin_user: User = Depends(require_admin_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user
