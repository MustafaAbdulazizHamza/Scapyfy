"""
API endpoints for message history management.

Provides secure access to user's conversation history with encryption.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from database import get_db
from models import User
from oauth2 import get_current_active_user
import schemas
import message_repository as msg_repo
from logger import get_logger

logger = get_logger()

router = APIRouter(
    prefix="/messages",
    tags=["message-history"],
    dependencies=[Depends(get_current_active_user)]
)


@router.post("/store", response_model=schemas.MessageHistoryResponse)
def store_message(
    request: schemas.MessageHistoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Store a message in conversation history."""
    try:
        message = msg_repo.store_message(
            db=db,
            user_id=current_user.id,
            conversation_id=request.conversation_id,
            role=request.role,
            content=request.content,
            content_type=request.content_type,
            tool_name=request.tool_name,
            tool_call_id=request.tool_call_id,
            session_id=request.session_id,
            provider_used=request.provider_used,
            tokens_used=request.tokens_used,
            execution_time_ms=request.execution_time_ms,
            metadata=request.metadata
        )
        
        logger.log_app_event(
            "message_stored",
            {
                "user": current_user.username,
                "conversation_id": request.conversation_id,
                "role": request.role
            }
        )
        
        return schemas.MessageHistoryResponse(
            id=message.id,
            role=message.role,
            content=request.content,  # Return unencrypted for confirmation
            content_type=message.content_type,
            tool_name=message.tool_name,
            tool_call_id=message.tool_call_id,
            session_id=message.session_id,
            provider_used=message.provider_used,
            tokens_used=message.tokens_used,
            execution_time_ms=message.execution_time_ms,
            metadata=request.metadata,
            created_at=message.created_at.isoformat() if message.created_at else None
        )
    except Exception as e:
        logger.app_logger.error(f"Failed to store message: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store message: {str(e)}"
        )


@router.post("/conversation/history")
def get_conversation_history(
    request: schemas.ConversationHistoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Retrieve and decrypt conversation history."""
    try:
        messages = msg_repo.get_conversation_history(
            db=db,
            user_id=current_user.id,
            conversation_id=request.conversation_id,
            limit=request.limit,
            include_archived=request.include_archived
        )
        
        logger.log_app_event(
            "conversation_retrieved",
            {
                "user": current_user.username,
                "conversation_id": request.conversation_id,
                "message_count": len(messages)
            }
        )
        
        return {
            "conversation_id": request.conversation_id,
            "messages": messages,
            "message_count": len(messages)
        }
    except Exception as e:
        logger.app_logger.error(f"Failed to retrieve conversation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve conversation: {str(e)}"
        )


@router.get("/conversations")
def list_conversations(
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get list of all conversations for the current user."""
    try:
        conversations = msg_repo.get_all_conversations(
            db=db,
            user_id=current_user.id,
            include_archived=include_archived
        )
        
        return schemas.ConversationListResponse(
            conversations=conversations,
            total_conversations=len(conversations)
        )
    except Exception as e:
        logger.app_logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list conversations: {str(e)}"
        )


@router.post("/conversation/{conversation_id}/archive")
def archive_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Archive a conversation."""
    try:
        success = msg_repo.archive_conversation(
            db=db,
            user_id=current_user.id,
            conversation_id=conversation_id
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to archive conversation")
        
        logger.log_app_event(
            "conversation_archived",
            {
                "user": current_user.username,
                "conversation_id": conversation_id
            }
        )
        
        return {"message": f"Conversation '{conversation_id}' archived successfully"}
    except Exception as e:
        logger.app_logger.error(f"Failed to archive conversation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to archive conversation: {str(e)}"
        )


@router.delete("/conversation/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Delete a conversation (hard delete)."""
    try:
        success = msg_repo.delete_conversation(
            db=db,
            user_id=current_user.id,
            conversation_id=conversation_id
        )
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to delete conversation")
        
        logger.log_app_event(
            "conversation_deleted",
            {
                "user": current_user.username,
                "conversation_id": conversation_id
            }
        )
        
        return {"message": f"Conversation '{conversation_id}' deleted successfully"}
    except Exception as e:
        logger.app_logger.error(f"Failed to delete conversation: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete conversation: {str(e)}"
        )


@router.get("/statistics", response_model=schemas.MessageStatisticsResponse)
def get_statistics(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get message statistics for the current user."""
    try:
        stats = msg_repo.get_message_statistics(
            db=db,
            user_id=current_user.id,
            days=days
        )
        
        return schemas.MessageStatisticsResponse(**stats)
    except Exception as e:
        logger.app_logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}"
        )
