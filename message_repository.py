"""
Message history repository - handles database operations for message storage and retrieval.
"""

import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from models import MessageHistory, User
from logger import get_logger

logger = get_logger()


def store_message(
    db: Session,
    user_id: int,
    conversation_id: str,
    role: str,
    content: str,
    content_type: str = "text",
    tool_name: Optional[str] = None,
    tool_call_id: Optional[str] = None,
    session_id: Optional[str] = None,
    provider_used: Optional[str] = None,
    tokens_used: Optional[int] = None,
    execution_time_ms: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> MessageHistory:
    """
    Store an encrypted message in the database.
    
    Args:
        db: Database session
        user_id: ID of the user
        conversation_id: Unique conversation identifier
        role: Message role ('user', 'assistant', 'system', 'tool')
        content: Message content
        content_type: Type of content ('text', 'json', 'report')
        tool_name: Optional tool used
        tool_call_id: Optional tool call identifier
        session_id: Optional session identifier
        provider_used: Optional LLM provider used
        tokens_used: Optional token count
        execution_time_ms: Optional execution time in milliseconds
        metadata: Optional additional metadata dictionary
        
    Returns:
        Created MessageHistory record
    """
    try:
        # Store content directly without encryption, but encode to bytes for LargeBinary column
        encrypted_content = content.encode('utf-8') if isinstance(content, str) else content
        
        # Encrypt metadata if provided
        metadata_json = None
        if metadata:
            metadata_json = json.dumps(metadata)
        
        message = MessageHistory(
            user_id=user_id,
            conversation_id=conversation_id,
            role=role,
            content_encrypted=encrypted_content,
            content_type=content_type,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            session_id=session_id,
            provider_used=provider_used,
            tokens_used=tokens_used,
            execution_time_ms=execution_time_ms,
            message_metadata=metadata_json
        )
        
        db.add(message)
        db.commit()
        db.refresh(message)
        
        logger.app_logger.info(f"Stored message: user={user_id}, conversation={conversation_id}, role={role}")
        return message
    except Exception as e:
        db.rollback()
        logger.app_logger.error(f"Failed to store message: {e}")
        raise


def get_conversation_history(
    db: Session,
    user_id: int,
    conversation_id: str,
    limit: Optional[int] = None,
    include_archived: bool = False
) -> List[Dict[str, Any]]:
    """
    Retrieve and decrypt conversation history.
    
    Args:
        db: Database session
        user_id: ID of the user
        conversation_id: Conversation identifier
        limit: Maximum number of messages to retrieve (None = all)
        include_archived: Whether to include archived messages
        
    Returns:
        List of decrypted message dictionaries
    """
    try:
        query = db.query(MessageHistory).filter(
            and_(
                MessageHistory.user_id == user_id,
                MessageHistory.conversation_id == conversation_id,
                MessageHistory.is_archived == (True if include_archived else False)
            )
        ).order_by(desc(MessageHistory.created_at))
        
        if limit:
            query = query.limit(limit)
        
        messages = query.all()
        
        # Return all messages without decryption
        result = []
        for msg in reversed(messages):  # Return in chronological order
            metadata_dict = {}
            if msg.message_metadata:
                try:
                    metadata_dict = json.loads(msg.message_metadata)
                except:
                    pass
            
            # Decode bytes to string
            content_str = msg.content_encrypted.decode('utf-8') if isinstance(msg.content_encrypted, bytes) else str(msg.content_encrypted)
            
            result.append({
                "id": msg.id,
                "role": msg.role,
                "content": content_str,  # Plaintext string now
                "content_type": msg.content_type,
                "tool_name": msg.tool_name,
                "tool_call_id": msg.tool_call_id,
                "session_id": msg.session_id,
                "provider_used": msg.provider_used,
                "tokens_used": msg.tokens_used,
                "execution_time_ms": msg.execution_time_ms,
                "metadata": metadata_dict,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            })
        
        return result
    except Exception as e:
        logger.app_logger.error(f"Failed to retrieve conversation history: {e}")
        raise


def get_all_conversations(
    db: Session,
    user_id: int,
    include_archived: bool = False
) -> List[Dict[str, Any]]:
    """
    Get list of all conversations for a user.
    
    Args:
        db: Database session
        user_id: ID of the user
        include_archived: Whether to include archived conversations
        
    Returns:
        List of conversation summaries
    """
    try:
        query = db.query(
            MessageHistory.conversation_id,
            MessageHistory.session_id,
            MessageHistory.provider_used
        ).filter(
            and_(
                MessageHistory.user_id == user_id,
                MessageHistory.is_archived == (True if include_archived else False)
            )
        ).group_by(
            MessageHistory.conversation_id,
            MessageHistory.session_id,
            MessageHistory.provider_used
        ).order_by(desc(MessageHistory.created_at))
        
        results = []
        seen = set()
        
        for row in query.all():
            conv_id = row[0]
            if conv_id not in seen:
                seen.add(conv_id)
                
                # Get message count and timestamps
                count = db.query(MessageHistory).filter(
                    and_(
                        MessageHistory.user_id == user_id,
                        MessageHistory.conversation_id == conv_id,
                        MessageHistory.is_archived == (True if include_archived else False)
                    )
                ).count()
                
                first_msg = db.query(MessageHistory).filter(
                    and_(
                        MessageHistory.user_id == user_id,
                        MessageHistory.conversation_id == conv_id
                    )
                ).order_by(MessageHistory.created_at).first()
                
                last_msg = db.query(MessageHistory).filter(
                    and_(
                        MessageHistory.user_id == user_id,
                        MessageHistory.conversation_id == conv_id
                    )
                ).order_by(desc(MessageHistory.created_at)).first()
                
                title = None
                if first_msg:
                    try:
                        content_str = first_msg.content_encrypted.decode('utf-8') if isinstance(first_msg.content_encrypted, bytes) else str(first_msg.content_encrypted)
                        title = content_str[:50] + ("..." if len(content_str) > 50 else "")
                    except:
                        pass
                
                results.append({
                    "conversation_id": conv_id,
                    "title": title,
                    "session_id": row[1],
                    "provider": row[2],
                    "message_count": count,
                    "started_at": first_msg.created_at.isoformat() if first_msg and first_msg.created_at else None,
                    "last_message_at": last_msg.created_at.isoformat() if last_msg and last_msg.created_at else None
                })
        
        return results
    except Exception as e:
        logger.app_logger.error(f"Failed to retrieve conversations: {e}")
        raise


def archive_conversation(
    db: Session,
    user_id: int,
    conversation_id: str
) -> bool:
    """
    Archive all messages in a conversation.
    
    Args:
        db: Database session
        user_id: ID of the user
        conversation_id: Conversation identifier
        
    Returns:
        Success status
    """
    try:
        db.query(MessageHistory).filter(
            and_(
                MessageHistory.user_id == user_id,
                MessageHistory.conversation_id == conversation_id
            )
        ).update({MessageHistory.is_archived: True})
        
        db.commit()
        logger.info(f"Archived conversation: user={user_id}, conversation={conversation_id}")
        return True
    except Exception as e:
        db.rollback()
        logger.app_logger.error(f"Failed to archive conversation: {e}")
        return False


def delete_conversation(
    db: Session,
    user_id: int,
    conversation_id: str
) -> bool:
    """
    Delete all messages in a conversation (hard delete).
    
    Args:
        db: Database session
        user_id: ID of the user
        conversation_id: Conversation identifier
        
    Returns:
        Success status
    """
    try:
        db.query(MessageHistory).filter(
            and_(
                MessageHistory.user_id == user_id,
                MessageHistory.conversation_id == conversation_id
            )
        ).delete()
        
        db.commit()
        logger.info(f"Deleted conversation: user={user_id}, conversation={conversation_id}")
        return True
    except Exception as e:
        db.rollback()
        logger.app_logger.error(f"Failed to delete conversation: {e}")
        return False


def cleanup_old_messages(
    db: Session,
    user_id: Optional[int] = None,
    older_than_days: int = 90,
    archive_instead_of_delete: bool = True
) -> int:
    """
    Clean up old messages (older than specified days).
    
    Args:
        db: Database session
        user_id: Optional specific user (None = all users)
        older_than_days: Delete messages older than this many days
        archive_instead_of_delete: Archive instead of deleting if True
        
    Returns:
        Number of messages affected
    """
    try:
        cutoff_date = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(days=older_than_days)
        
        query = db.query(MessageHistory).filter(MessageHistory.created_at < cutoff_date)
        
        if user_id:
            query = query.filter(MessageHistory.user_id == user_id)
        
        count = query.count()
        
        if archive_instead_of_delete:
            query.update({MessageHistory.is_archived: True})
        else:
            query.delete()
        
        db.commit()
        logger.info(f"Cleaned up {count} old messages (older than {older_than_days} days)")
        return count
    except Exception as e:
        db.rollback()
        logger.app_logger.error(f"Failed to cleanup old messages: {e}")
        return 0


def get_message_statistics(
    db: Session,
    user_id: int,
    days: int = 30
) -> Dict[str, Any]:
    """
    Get message statistics for a user.
    
    Args:
        db: Database session
        user_id: ID of the user
        days: Number of days to look back
        
    Returns:
        Statistics dictionary
    """
    try:
        cutoff_date = datetime.now(datetime.now().astimezone().tzinfo) - timedelta(days=days)
        
        total_messages = db.query(MessageHistory).filter(
            and_(
                MessageHistory.user_id == user_id,
                MessageHistory.created_at >= cutoff_date,
                MessageHistory.is_archived == False
            )
        ).count()
        
        user_messages = db.query(MessageHistory).filter(
            and_(
                MessageHistory.user_id == user_id,
                MessageHistory.role == "user",
                MessageHistory.created_at >= cutoff_date,
                MessageHistory.is_archived == False
            )
        ).count()
        
        assistant_messages = db.query(MessageHistory).filter(
            and_(
                MessageHistory.user_id == user_id,
                MessageHistory.role == "assistant",
                MessageHistory.created_at >= cutoff_date,
                MessageHistory.is_archived == False
            )
        ).count()
        
        total_tokens = db.query(MessageHistory).filter(
            and_(
                MessageHistory.user_id == user_id,
                MessageHistory.tokens_used != None,
                MessageHistory.created_at >= cutoff_date,
                MessageHistory.is_archived == False
            )
        ).all()
        
        total_tokens_used = sum(m.tokens_used for m in total_tokens if m.tokens_used)
        
        conversations = db.query(MessageHistory.conversation_id).filter(
            and_(
                MessageHistory.user_id == user_id,
                MessageHistory.created_at >= cutoff_date,
                MessageHistory.is_archived == False
            )
        ).group_by(MessageHistory.conversation_id).count()
        
        return {
            "period_days": days,
            "total_messages": total_messages,
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "total_tokens_used": total_tokens_used,
            "conversations_count": conversations,
            "average_messages_per_conversation": total_messages // conversations if conversations > 0 else 0
        }
    except Exception as e:
        logger.app_logger.error(f"Failed to get message statistics: {e}")
        raise
