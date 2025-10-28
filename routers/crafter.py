from fastapi import APIRouter, Depends, HTTPException
from rich.diagnose import report
from Scapyfy.logic import loop
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
    """Active packet crafting endpoint"""

    try:

        report = loop.llm_crafter(prompt=craft_request.prompt, user=current_user.username, max_iterations=craft_request.max_iterations)

        return schemas.CraftingResponse(
            success=True,
            report=report
        )
    except Exception as e:
        raise HTTPException(status_code=500,
                            detail=f"Failed to craft packet: {str(e)}")


@router.post("/passive_craft", response_model=schemas.Passive_CraftingResponse)
def passively_craft_packet(
        craft_request: schemas.Passive_CraftingRequest,
        current_user: User = Depends(get_current_active_user)
):
    """Passive packet crafting endpoint"""
    try:
        pkt = loop.llm_crafter(prompt=f"Passively craft the following: {craft_request.packet_description}", user=current_user.username, max_iterations=2)

        return schemas.Passive_CraftingResponse(
            success=True,
            packet_json=pkt
        )
    except Exception as e:
        raise HTTPException(status_code=500,
            detail=f"Failed to craft the requested packet: {str(e)}",
        )

@router.get("/status")
def get_crafter_status(current_user: User = Depends(get_current_active_user)):
    """Get crafting status"""
    return {
        "user_id": current_user.id,
        "username": current_user.username,
        "status": "ready",
        "active_sessions": 0,
        "passive_sessions": 0
    }