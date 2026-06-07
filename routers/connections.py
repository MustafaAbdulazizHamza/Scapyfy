from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import json
import secrets

from database import get_db
from models import User, Connection, BotAuth
from oauth2 import get_current_active_user
from logic.connections import test_connection, push_to_connection, ConnectionError as ConnError
from logger import get_logger
import schemas

router = APIRouter(
    prefix="/connections",
    tags=["connections"],
    dependencies=[Depends(get_current_active_user)]
)

logger = get_logger()

VALID_CONN_TYPES = ['mongodb', 'elasticsearch', 'telegram']
BOT_CONN_TYPES = ['telegram']
SENSITIVE_KEYS = ['password', 'token', 'secret', 'key']


def _mask_config(config: dict) -> dict:
    """Mask sensitive fields in a connection config for list responses."""
    masked = {}
    for k, v in config.items():
        if not isinstance(v, str):
            masked[k] = v
            continue
        # Mask keys that contain sensitive substrings
        if any(s in k.lower() for s in SENSITIVE_KEYS):
            masked[k] = '***'
        elif k.lower() == 'uri' and '@' in v:
            masked[k] = '***'
        else:
            masked[k] = v
    return masked


def _conn_to_response(conn: Connection, mask: bool = False) -> dict:
    """Convert a Connection ORM object to a response dict with parsed config."""
    try:
        config = json.loads(conn.config)
    except (json.JSONDecodeError, TypeError):
        config = {}

    if mask:
        config = _mask_config(config)

    return {
        "id": conn.id,
        "user_id": conn.user_id,
        "name": conn.name,
        "conn_type": conn.conn_type,
        "config": config,
        "is_active": conn.is_active,
        "created_at": conn.created_at,
    }


def _get_user_connection(db: Session, connection_id: int, user: User) -> Connection:
    """Fetch a connection and verify it belongs to the current user."""
    conn = db.query(Connection).filter(Connection.id == connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
    if conn.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this connection")
    return conn


# ============================================================
# CRUD Endpoints
# ============================================================

@router.post("/", response_model=schemas.ConnectionResponse)
def create_connection(
        conn_data: schemas.ConnectionCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    if conn_data.conn_type not in VALID_CONN_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid connection type. Valid types: {VALID_CONN_TYPES}"
        )

    try:
        new_conn = Connection(
            user_id=current_user.id,
            name=conn_data.name,
            conn_type=conn_data.conn_type,
            config=json.dumps(conn_data.config),
        )
        db.add(new_conn)
        db.commit()
        db.refresh(new_conn)

        logger.log_app_event("connection_created", {"message": f"User '{current_user.username}' created connection '{conn_data.name}' ({conn_data.conn_type})"})
        return _conn_to_response(new_conn)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create connection: {str(e)}")


@router.get("/", response_model=List[schemas.ConnectionResponse])
def list_connections(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    connections = db.query(Connection).filter(Connection.user_id == current_user.id).all()
    return [_conn_to_response(c, mask=True) for c in connections]


@router.get("/{connection_id}", response_model=schemas.ConnectionResponse)
def get_connection(
        connection_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    conn = _get_user_connection(db, connection_id, current_user)
    return _conn_to_response(conn, mask=False)


@router.put("/{connection_id}", response_model=schemas.ConnectionResponse)
def update_connection(
        connection_id: int,
        conn_data: schemas.ConnectionUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    conn = _get_user_connection(db, connection_id, current_user)

    try:
        if conn_data.name is not None:
            conn.name = conn_data.name
        if conn_data.config is not None:
            conn.config = json.dumps(conn_data.config)
        if conn_data.is_active is not None:
            conn.is_active = conn_data.is_active

        db.commit()
        db.refresh(conn)

        logger.log_app_event("connection_updated", {"message": f"User '{current_user.username}' updated connection '{conn.name}' (id={conn.id})"})
        return _conn_to_response(conn)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update connection: {str(e)}")


@router.delete("/{connection_id}")
def delete_connection(
        connection_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    conn = _get_user_connection(db, connection_id, current_user)

    try:
        conn_name = conn.name
        # Also delete associated bot auths
        db.query(BotAuth).filter(BotAuth.connection_id == connection_id).delete()
        db.delete(conn)
        db.commit()

        logger.log_app_event("connection_deleted", {"message": f"User '{current_user.username}' deleted connection '{conn_name}' (id={connection_id})"})
        return {"message": f"Connection '{conn_name}' deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete connection: {str(e)}")


# ============================================================
# Test & Export Endpoints
# ============================================================

@router.post("/{connection_id}/test")
def test_connection_endpoint(
        connection_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    conn = _get_user_connection(db, connection_id, current_user)

    try:
        config = json.loads(conn.config)
        result = test_connection(conn.conn_type, config)
        message = "Connection successful" if result else "Connection failed"
        return {"success": result, "message": message}
    except ConnError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")


@router.post("/export", response_model=schemas.ExportResponse)
def export_to_connection(
        export_data: schemas.ExportRequest,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    conn = _get_user_connection(db, export_data.connection_id, current_user)

    if not conn.is_active:
        raise HTTPException(status_code=400, detail="Connection is inactive")

    try:
        config = json.loads(conn.config)
        
        # Build metadata from request
        metadata = export_data.metadata or {}
        if export_data.source:
            metadata["source"] = export_data.source
            
        # Try to extract tool_name from data if not present in metadata
        if "tool_name" not in metadata and isinstance(export_data.content, dict):
            if "tool" in export_data.content:
                metadata["tool_name"] = export_data.content["tool"]

        result = push_to_connection(
            conn_type=conn.conn_type,
            config=config,
            data=export_data.content,
            metadata=metadata
        )

        logger.log_app_event("connection_exported", {
            "message": f"User '{current_user.username}' exported data to connection '{conn.name}' (type={conn.conn_type}, source={export_data.source})"
        })

        return schemas.ExportResponse(
            success=result.get("success", False),
            connection_id=conn.id,
            connection_name=conn.name,
            message=result.get("message", "Export completed")
        )
    except ConnError as e:
        raise HTTPException(status_code=502, detail=f"Export failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


# ============================================================
# Bot Auth Endpoints
# ============================================================

@router.post("/{connection_id}/generate-hash", response_model=schemas.BotAuthResponse)
def generate_bot_auth_hash(
        connection_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    conn = _get_user_connection(db, connection_id, current_user)

    if conn.conn_type not in BOT_CONN_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Auth hash generation is only supported for bot connections ({BOT_CONN_TYPES})"
        )

    try:
        auth_hash = secrets.token_hex(32)  # 64-char hex string

        bot_auth = BotAuth(
            user_id=current_user.id,
            connection_id=conn.id,
            auth_hash=auth_hash,
        )
        db.add(bot_auth)
        db.commit()
        db.refresh(bot_auth)

        logger.log_app_event("bot_auth_generated", {
            "message": f"User '{current_user.username}' generated auth hash for connection '{conn.name}' (id={conn.id})"
        })
        return bot_auth
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to generate auth hash: {str(e)}")


@router.get("/bot-auths/{connection_id}", response_model=List[schemas.BotAuthResponse])
def list_bot_auths(
        connection_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    conn = _get_user_connection(db, connection_id, current_user)

    auths = db.query(BotAuth).filter(
        BotAuth.connection_id == conn.id,
        BotAuth.user_id == current_user.id
    ).all()
    return auths


@router.delete("/bot-auths/{auth_id}")
def revoke_bot_auth(
        auth_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user)
):
    bot_auth = db.query(BotAuth).filter(BotAuth.id == auth_id).first()
    if not bot_auth:
        raise HTTPException(status_code=404, detail="Bot auth not found")
    if bot_auth.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to revoke this auth hash")

    try:
        db.delete(bot_auth)
        db.commit()

        logger.log_app_event("bot_auth_revoked", {"message": f"User '{current_user.username}' revoked bot auth (id={auth_id})"})
        return {"message": "Bot auth hash revoked successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to revoke auth hash: {str(e)}")


public_router = APIRouter(
    prefix="/connections/bot",
    tags=["connections-bot"]
)

@public_router.post("/bind")
def bind_bot_account(
        bind_data: schemas.BotBindRequest,
        db: Session = Depends(get_db)
):
    bot_auth = db.query(BotAuth).filter(BotAuth.auth_hash == bind_data.auth_hash).first()
    if not bot_auth:
        raise HTTPException(status_code=404, detail="Invalid auth hash")
    
    if bot_auth.is_bound:
        raise HTTPException(status_code=400, detail="Hash already bound")
        
    conn = db.query(Connection).filter(Connection.id == bot_auth.connection_id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Connection not found")
        
    try:
        config = json.loads(conn.config) if isinstance(conn.config, str) else conn.config
        
        if conn.conn_type == "telegram":
            chat_ids = config.setdefault("chat_ids", [])
            if bind_data.external_user_id not in chat_ids:
                chat_ids.append(bind_data.external_user_id)
        
        conn.config = json.dumps(config)
        bot_auth.is_bound = True
        bot_auth.external_user_id = bind_data.external_user_id
        
        db.commit()
        
        logger.log_app_event("account_bound", {
            "message": f"Bound {conn.conn_type} account {bind_data.external_user_id} to connection '{conn.name}'"
        })
        
        return {"success": True, "message": f"Successfully bound to {conn.name}"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to bind: {str(e)}")
