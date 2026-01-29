from fastapi import APIRouter, Depends, HTTPException
from logic import loop
from models import User
from oauth2 import get_current_active_user
import schemas

router = APIRouter(
    tags=["packet-crafting"],
    dependencies=[Depends(get_current_active_user)]
)


@router.post("/craft", response_model=schemas.CraftingResponse)
def craft_packet(
        craft_request: schemas.CraftingRequest,
        current_user: User = Depends(get_current_active_user)
):
    try:
        report = loop.llm_crafter(
            prompt_text=craft_request.prompt,
            user=current_user.username,
            max_iterations=craft_request.max_iterations,
            provider_name=craft_request.provider,
            memory_context=craft_request.memory_context
        )
        
        return schemas.CraftingResponse(
            success=True,
            report=report,
            provider=craft_request.provider or "auto"
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
        current_user: User = Depends(get_current_active_user)
):
    try:
        pkt = loop.llm_crafter(
            prompt=f"Passively craft the following (return JSON structure only, do not send): {craft_request.packet_description}",
            user=current_user.username,
            max_iterations=2,
            provider_name=craft_request.provider
        )
        
        return schemas.PassiveCraftingResponse(
            success=True,
            packet_json=pkt,
            provider=craft_request.provider or "auto"
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
