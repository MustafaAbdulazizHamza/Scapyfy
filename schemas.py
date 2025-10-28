from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# User schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Authentication schemas
class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    username: str


class TokenData(BaseModel):
    user_id: Optional[int] = None


# Crafter schemas
class CraftingRequest(BaseModel):
    max_iterations: Optional[int] = 4
    prompt: str


class CraftingResponse(BaseModel):
    success: bool
    report: str
class Passive_CraftingRequest(BaseModel):
    packet_description: str
class Passive_CraftingResponse(BaseModel):
    success: bool
    packet_json: str
