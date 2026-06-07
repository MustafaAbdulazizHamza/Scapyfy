import re
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


class UserBase(BaseModel):
    username: str
    email: EmailStr
    avatar_data: Optional[str] = None

    @field_validator('avatar_data')
    @classmethod
    def validate_avatar_data(cls, v):
        if v is None:
            return v
        if len(v) > 700000:
            raise ValueError('Avatar file is too large.')
        if not re.match(r'^data:image/(jpeg|png|webp|gif);base64,[A-Za-z0-9+/=]+$', v):
            raise ValueError('Invalid image format or encoding. Only JPEG, PNG, WEBP, and GIF are allowed.')
        return v


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
    conversation_id: Optional[str] = None
    memory_context: Optional[str] = None  # LLM-summarized context from previous interactions
    mode: Optional[str] = "agent"  # 'agent' or 'ask'
    
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
    memory_summary: Optional[str] = None  # LLM-generated summary for next interaction
    conversation_id: Optional[str] = None  # Conversation identifier for message history


class SummarizeRequest(BaseModel):
    messages: list  # List of {type: 'user'|'assistant', content: str}
    previous_summary: Optional[str] = None
    provider: Optional[str] = None


class SummarizeResponse(BaseModel):
    summary: str
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
    conversation_id: Optional[str] = None  # Conversation identifier for message history


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


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    avatar_data: Optional[str] = None

    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        if v is not None and len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v
        
    @field_validator('avatar_data')
    @classmethod
    def validate_avatar_data(cls, v):
        if v is None:
            return v
        if len(v) > 700000:
            raise ValueError('Avatar file is too large.')
        if not re.match(r'^data:image/(jpeg|png|webp|gif);base64,[A-Za-z0-9+/=]+$', v):
            raise ValueError('Invalid image format or encoding. Only JPEG, PNG, WEBP, and GIF are allowed.')
        return v
    
class SetupRequest(BaseModel):
    password: str
    email: EmailStr
    
    @field_validator('password')
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


# ============================================================
# Connection Schemas
# ============================================================

class ConnectionCreate(BaseModel):
    name: str
    conn_type: str  # 'mongodb', 'elasticsearch', 'telegram'
    config: Dict[str, Any]

    @field_validator('conn_type')
    @classmethod
    def validate_conn_type(cls, v):
        valid_types = ['mongodb', 'elasticsearch', 'telegram']
        if v.lower() not in valid_types:
            raise ValueError(f'Invalid connection type. Valid: {valid_types}')
        return v.lower()


class ConnectionUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ConnectionResponse(BaseModel):
    id: int
    user_id: int
    name: str
    conn_type: str
    config: Dict[str, Any]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# Task Schemas
# ============================================================

class TaskStep(BaseModel):
    """A single step in a task. Either a tool call or a prompt."""
    type: str  # 'tool' or 'prompt'
    tool_name: Optional[str] = None  # required if type == 'tool'
    parameters: Optional[Dict[str, Any]] = None  # tool parameters
    prompt_text: Optional[str] = None  # required if type == 'prompt'

    @field_validator('type')
    @classmethod
    def validate_step_type(cls, v):
        if v not in ('tool', 'prompt'):
            raise ValueError('Step type must be "tool" or "prompt"')
        return v


class ScheduleConfig(BaseModel):
    """Schedule configuration for a task."""
    schedule_type: str  # 'once', 'interval', 'cron'
    run_at: Optional[str] = None  # ISO datetime for 'once'
    interval_seconds: Optional[int] = None  # for 'interval'
    cron_expression: Optional[str] = None  # for 'cron' (5-field)
    max_runs: Optional[int] = None  # null = unlimited

    @field_validator('schedule_type')
    @classmethod
    def validate_schedule_type(cls, v):
        if v not in ('once', 'interval', 'cron'):
            raise ValueError('Schedule type must be "once", "interval", or "cron"')
        return v


class TaskCreate(BaseModel):
    name: str
    description: Optional[str] = None
    steps: List[TaskStep]
    schedule: ScheduleConfig
    output_connections: Optional[List[int]] = None  # list of connection IDs
    provider: Optional[str] = None  # LLM provider for prompt steps


class TaskUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[List[TaskStep]] = None
    schedule: Optional[ScheduleConfig] = None
    output_connections: Optional[List[int]] = None
    is_active: Optional[bool] = None


class TaskResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str]
    steps: List[TaskStep]
    schedule_type: str
    schedule_config: Dict[str, Any]
    max_runs: Optional[int]
    run_count: int
    output_connections: Optional[List[int]]
    is_active: bool
    next_run_at: Optional[datetime]
    last_run_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class TaskRunResponse(BaseModel):
    id: int
    task_id: int
    user_id: int
    status: str
    steps_log: Optional[List[Dict[str, Any]]]
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# Export / Output Routing Schemas
# ============================================================

class ExportRequest(BaseModel):
    connection_id: int
    content: Dict[str, Any]  # The output data to export
    source: Optional[str] = None  # 'chat', 'tool', 'task'
    metadata: Optional[Dict[str, Any]] = None


class ExportResponse(BaseModel):
    success: bool
    connection_id: int
    connection_name: str
    message: str


# ============================================================
# Bot Auth Schemas
# ============================================================

class BotAuthGenerate(BaseModel):
    connection_id: int


class BotBindRequest(BaseModel):
    auth_hash: str
    external_user_id: str


class BotAuthResponse(BaseModel):
    id: int
    connection_id: int
    auth_hash: str
    is_bound: bool
    external_user_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# Message History Schemas
class MessageHistoryCreate(BaseModel):
    """Request to store a message."""
    conversation_id: str
    role: str  # 'user', 'assistant', 'system', 'tool'
    content: str
    content_type: str = "text"  # 'text', 'json', 'report'
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    session_id: Optional[str] = None
    provider_used: Optional[str] = None
    tokens_used: Optional[int] = None
    execution_time_ms: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class MessageHistoryResponse(BaseModel):
    """Response with decrypted message."""
    id: int
    role: str
    content: str
    content_type: str
    tool_name: Optional[str]
    tool_call_id: Optional[str]
    session_id: Optional[str]
    provider_used: Optional[str]
    tokens_used: Optional[int]
    execution_time_ms: Optional[int]
    metadata: Optional[Dict[str, Any]]
    created_at: Optional[str]


class ConversationHistoryRequest(BaseModel):
    """Request to retrieve conversation history."""
    conversation_id: str
    limit: Optional[int] = None
    include_archived: bool = False


class ConversationSummary(BaseModel):
    """Summary of a conversation."""
    conversation_id: str
    title: Optional[str] = None
    session_id: Optional[str]
    provider: Optional[str]
    message_count: int
    started_at: Optional[str]
    last_message_at: Optional[str]


class ConversationListResponse(BaseModel):
    """Response with list of user's conversations."""
    conversations: List[ConversationSummary]
    total_conversations: int


class MessageStatisticsResponse(BaseModel):
    """Statistics about user's messages."""
    period_days: int
    total_messages: int
    user_messages: int
    assistant_messages: int
    total_tokens_used: int
    conversations_count: int
    average_messages_per_conversation: int
