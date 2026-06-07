from fastapi import APIRouter, Depends, HTTPException
from logic import loop
from models import User
from oauth2 import get_current_active_user
import schemas
from database import get_db
from sqlalchemy.orm import Session
import uuid
import message_repository as msg_repo

router = APIRouter(
    tags=["packet-crafting"],
    dependencies=[Depends(get_current_active_user)]
)


@router.post("/craft", response_model=schemas.CraftingResponse)
def craft_packet(
        craft_request: schemas.CraftingRequest,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    try:
        # Generate conversation ID if not provided
        conversation_id = craft_request.conversation_id or str(uuid.uuid4())[:12]
        
        # Fetch conversation history to build memory context BEFORE storing the new message
        history = msg_repo.get_conversation_history(
            db=db,
            user_id=current_user.id,
            conversation_id=conversation_id,
            limit=10
        )
        
        # Store user message
        msg_repo.store_message(
            db=db,
            user_id=current_user.id,
            conversation_id=conversation_id,
            role="user",
            content=craft_request.prompt,
            content_type="text",
            session_id=str(uuid.uuid4())[:8],
            provider_used=craft_request.provider or "auto"
        )
        
        # Build memory context string from history (reverse it because get_conversation_history returns newest first, but it already reverses them internally)
        memory_context = ""
        if history:
            memory_context = "Previous Conversation History:\n"
            for msg in history:
                role = "User" if msg["role"] == "user" else "Assistant"
                memory_context += f"{role}: {msg['content']}\n\n"
        
        # Generate report
        report = loop.llm_crafter(
            prompt_text=craft_request.prompt,
            user=current_user.username,
            max_iterations=craft_request.max_iterations,
            provider_name=craft_request.provider,
            memory_context=memory_context if memory_context else None,
            mode=craft_request.mode
        )
        
        # Store assistant response
        msg_repo.store_message(
            db=db,
            user_id=current_user.id,
            conversation_id=conversation_id,
            role="assistant",
            content=report,
            content_type="report",
            provider_used=craft_request.provider or "auto"
        )
        
        return schemas.CraftingResponse(
            success=True,
            report=report,
            provider=craft_request.provider or "auto",
            conversation_id=conversation_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to craft packet: {str(e)}"
        )


@router.post("/summarize", response_model=schemas.SummarizeResponse)
def summarize_chat(
        request: schemas.SummarizeRequest,
        current_user: User = Depends(get_current_active_user)
):
    """Generate a memory summary from chat messages for context preservation."""
    try:
        summary = loop.summarize_chat(
            messages=request.messages,
            previous_summary=request.previous_summary,
            provider_name=request.provider
        )
        
        return schemas.SummarizeResponse(
            summary=summary,
            provider=request.provider or "auto"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to summarize chat: {str(e)}"
        )


@router.post("/passive_craft", response_model=schemas.PassiveCraftingResponse)
def passively_craft_packet(
        craft_request: schemas.PassiveCraftingRequest,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    try:
        # Generate conversation ID if not provided
        conversation_id = str(uuid.uuid4())[:12]
        
        # Store user message
        msg_repo.store_message(
            db=db,
            user_id=current_user.id,
            conversation_id=conversation_id,
            role="user",
            content=f"Passively craft: {craft_request.packet_description}",
            content_type="text",
            session_id=str(uuid.uuid4())[:8],
            provider_used=craft_request.provider or "auto"
        )
        
        # Generate packet JSON
        pkt = loop.llm_crafter(
            prompt=f"Passively craft the following (return JSON structure only, do not send): {craft_request.packet_description}",
            user=current_user.username,
            max_iterations=2,
            provider_name=craft_request.provider
        )
        
        # Store assistant response
        msg_repo.store_message(
            db=db,
            user_id=current_user.id,
            conversation_id=conversation_id,
            role="assistant",
            content=pkt,
            content_type="json",
            provider_used=craft_request.provider or "auto"
        )
        
        return schemas.PassiveCraftingResponse(
            success=True,
            packet_json=pkt,
            provider=craft_request.provider or "auto",
            conversation_id=conversation_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to craft the requested packet: {str(e)}",
        )


@router.get("/status")
def get_crafter_status(current_user: User = Depends(get_current_active_user)):
    available_providers = loop.get_available_providers()
    
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "status": "ready",
        "available_providers": available_providers,
        "default_provider": available_providers[0] if available_providers else None
    }


@router.get("/providers")
def get_available_providers(current_user: User = Depends(get_current_active_user)):
    return {
        "providers": loop.get_available_providers(),
        "supported": ["openai", "gemini", "claude", "ollama"]
    }
