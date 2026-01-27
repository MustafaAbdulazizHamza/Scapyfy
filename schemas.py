from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


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


class CraftingRequest(BaseModel):
    prompt: str
    max_iterations: Optional[int] = 10
    provider: Optional[str] = None
    
    @field_validator('max_iterations')
    @classmethod
    def validate_iterations(cls, v):
        if v is not None and (v < 1 or v > 50):
            raise ValueError('max_iterations must be between 1 and 50')
        return v
    
    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v):
        if v is not None:
            valid_providers = ['openai', 'gemini', 'claude', 'ollama', 'google', 'anthropic']
            if v.lower() not in valid_providers:
                raise ValueError(f'Invalid provider. Valid options: {valid_providers}')
        return v.lower() if v else None


class CraftingResponse(BaseModel):
    success: bool
    report: str
    provider: Optional[str] = None


class PassiveCraftingRequest(BaseModel):
    packet_description: str
    provider: Optional[str] = None
    
    @field_validator('provider')
    @classmethod
    def validate_provider(cls, v):
        if v is not None:
            valid_providers = ['openai', 'gemini', 'claude', 'ollama', 'google', 'anthropic']
            if v.lower() not in valid_providers:
                raise ValueError(f'Invalid provider. Valid options: {valid_providers}')
        return v.lower() if v else None


class PassiveCraftingResponse(BaseModel):
    success: bool
    packet_json: str
    provider: Optional[str] = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str
    
    @field_validator('new_password')
    @classmethod
    def new_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('New password must be at least 8 characters')
        return v


class AdminPasswordChange(BaseModel):
    new_password: str
    
    @field_validator('new_password')
    @classmethod
    def new_password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('New password must be at least 8 characters')
        return v
