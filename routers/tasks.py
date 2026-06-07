from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from datetime import datetime, timezone

from database import get_db
from models import User, Task, TaskRun, Connection
from oauth2 import get_current_active_user
from logic.scheduler import schedule_task, unschedule_task
from logger import get_logger

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    dependencies=[Depends(get_current_active_user)]
)

logger = get_logger()

AVAILABLE_TOOLS = [
    'ping_host', 'nmap_scan', 'traceroute_host', 'quick_port_scan',
    'arp_scan', 'send_packet', 'hping3_probe', 'dns_lookup_tool', 'http_request'
]

TOOL_DESCRIPTIONS = {
    "ping_host": "Ping a host to check if it's reachable",
    "nmap_scan": "Perform an NMAP scan on a target",
    "traceroute_host": "Perform a traceroute to discover the path to a target",
    "quick_port_scan": "Perform a quick TCP port scan using Scapy",
    "arp_scan": "Perform an ARP scan to discover hosts on the local network",
    "send_packet": "Send a crafted packet using Scapy",
    "hping3_probe": "Use hping3 for advanced packet probing",
    "dns_lookup_tool": "Perform DNS lookups for various record types",
    "http_request": "Send an HTTP(s) request and get the response",
}


def _serialize_task(task: Task) -> dict:
    """Convert a Task model instance to a dict with JSON fields parsed."""
    steps = json.loads(task.steps) if isinstance(task.steps, str) else (task.steps or [])
    schedule_config = json.loads(task.schedule_config) if isinstance(task.schedule_config, str) else (task.schedule_config or {})
    output_conns = json.loads(task.output_connections) if task.output_connections else []

    return {
        "id": task.id,
        "user_id": task.user_id,
        "name": task.name,
        "description": task.description,
        "steps": steps,
        "schedule_type": task.schedule_type,
        "schedule_config": schedule_config,
        "max_runs": task.max_runs,
        "run_count": task.run_count,
        "output_connections": output_conns if isinstance(output_conns, list) else [],
        "is_active": task.is_active,
        "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
        "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


def _serialize_run(run: TaskRun) -> dict:
    """Convert a TaskRun model instance to a dict with JSON fields parsed."""
    steps_log = json.loads(run.steps_log) if isinstance(run.steps_log, str) else (run.steps_log or [])

    return {
        "id": run.id,
        "task_id": run.task_id,
        "user_id": run.user_id,
        "status": run.status,
        "steps_log": steps_log,
        "error_message": run.error_message,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def _validate_steps(steps: list):
    """Validate task steps structure and tool names."""
    if not steps:
        raise HTTPException(status_code=400, detail="At least one step is required")

    for i, step in enumerate(steps):
        step_type = step.get("type")
        if step_type not in ("tool", "prompt"):
            raise HTTPException(
                status_code=400,
                detail=f"Step {i}: type must be 'tool' or 'prompt', got '{step_type}'"
            )

        if step_type == "tool":
            tool_name = step.get("tool_name")
            if not tool_name:
                raise HTTPException(
                    status_code=400,
                    detail=f"Step {i}: 'tool_name' is required for tool steps"
                )
            if tool_name not in AVAILABLE_TOOLS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Step {i}: unknown tool '{tool_name}'. Available: {AVAILABLE_TOOLS}"
                )

        elif step_type == "prompt":
            if not step.get("prompt_text"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Step {i}: 'prompt_text' is required for prompt steps"
                )


def _validate_output_connections(connection_ids: list, user_id: int, db: Session):
    """Validate that output connection IDs exist and belong to the current user."""
    for conn_id in connection_ids:
        conn = db.query(Connection).filter(
            Connection.id == conn_id,
            Connection.user_id == user_id
        ).first()
        if not conn:
            raise HTTPException(
                status_code=400,
                detail=f"Connection {conn_id} not found or does not belong to you"
            )


# ---------------------------------------------------------------------------
# Available tools listing  (registered BEFORE parameterized routes)
# ---------------------------------------------------------------------------

@router.get("/available-tools")
def get_available_tools(current_user: User = Depends(get_current_active_user)):
    """Return the list of available tools that can be used as task steps."""
    return [
        {"name": tool, "description": TOOL_DESCRIPTIONS.get(tool, "")}
        for tool in AVAILABLE_TOOLS
    ]


@router.get("/runs/{run_id}")
def get_task_run(
        run_id: int,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    """Get a single task run by ID."""
    run = db.query(TaskRun).filter(TaskRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Task run not found")

    # Ensure the parent task belongs to the current user
    task = db.query(Task).filter(
        Task.id == run.task_id,
        Task.user_id == current_user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task run not found")

    return _serialize_run(run)


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------

@router.post("/")
def create_task(
        body: dict,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    """Create a new scheduled task."""
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="'name' is required")

    description = body.get("description")
    steps = body.get("steps")
    schedule = body.get("schedule")
    output_connections = body.get("output_connections", [])
    provider = body.get("provider")

    if not steps:
        raise HTTPException(status_code=400, detail="'steps' is required")
    if not schedule:
        raise HTTPException(status_code=400, detail="'schedule' is required")

    # Validate steps
    _validate_steps(steps)

    # Validate schedule
    schedule_type = schedule.get("schedule_type")
    if schedule_type not in ("once", "interval", "cron"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid schedule_type '{schedule_type}'. Must be 'once', 'interval', or 'cron'"
        )

    # Validate output connections
    if output_connections:
        _validate_output_connections(output_connections, current_user.id, db)

    # Build schedule config dict (includes provider for prompt steps)
    schedule_config = {
        "schedule_type": schedule_type,
        "run_at": schedule.get("run_at"),
        "interval_seconds": schedule.get("interval_seconds"),
        "cron_expression": schedule.get("cron_expression"),
        "provider": provider,
    }

    max_runs = schedule.get("max_runs")

    # Create the task
    task = Task(
        user_id=current_user.id,
        name=name,
        description=description,
        steps=json.dumps(steps),
        schedule_type=schedule_type,
        schedule_config=json.dumps(schedule_config),
        max_runs=max_runs,
        output_connections=json.dumps(output_connections) if output_connections else None,
        is_active=True,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Schedule the task
    try:
        schedule_task(task.id, schedule_type, schedule_config)
    except Exception as e:
        logger.log_tool_execution(
            user=current_user.username,
            tool_name="task_create",
            parameters={"task_id": task.id, "task_name": name},
            source="api",
            success=False,
            error=f"Created but scheduling failed: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Task created but scheduling failed: {str(e)}"
        )

    logger.log_tool_execution(
        user=current_user.username,
        tool_name="task_create",
        parameters={"task_id": task.id, "task_name": name},
        source="api",
        success=True,
        result_preview=f"Scheduled ({schedule_type})"
    )

    return _serialize_task(task)


@router.get("/")
def list_tasks(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    """List all tasks for the current user."""
    tasks = db.query(Task).filter(Task.user_id == current_user.id).all()
    return [_serialize_task(t) for t in tasks]


@router.get("/{task_id}")
def get_task(
        task_id: int,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    """Get a single task by ID."""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return _serialize_task(task)


@router.put("/{task_id}")
def update_task(
        task_id: int,
        body: dict,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    """Update an existing task."""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    needs_reschedule = False

    # Update name
    if "name" in body:
        task.name = body["name"]

    # Update description
    if "description" in body:
        task.description = body["description"]

    # Update steps
    if "steps" in body:
        _validate_steps(body["steps"])
        task.steps = json.dumps(body["steps"])

    # Update output connections
    if "output_connections" in body:
        output_connections = body["output_connections"] or []
        if output_connections:
            _validate_output_connections(output_connections, current_user.id, db)
        task.output_connections = json.dumps(output_connections) if output_connections else None

    # Update schedule
    if "schedule" in body:
        schedule = body["schedule"]
        schedule_type = schedule.get("schedule_type")
        if schedule_type and schedule_type not in ("once", "interval", "cron"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid schedule_type '{schedule_type}'. Must be 'once', 'interval', or 'cron'"
            )

        provider = body.get("provider")
        # Preserve existing provider if not provided
        if provider is None:
            try:
                existing_config = json.loads(task.schedule_config) if isinstance(task.schedule_config, str) else {}
                provider = existing_config.get("provider")
            except (json.JSONDecodeError, TypeError):
                provider = None

        schedule_config = {
            "schedule_type": schedule_type or task.schedule_type,
            "run_at": schedule.get("run_at"),
            "interval_seconds": schedule.get("interval_seconds"),
            "cron_expression": schedule.get("cron_expression"),
            "provider": provider,
        }

        if schedule_type:
            task.schedule_type = schedule_type
        task.schedule_config = json.dumps(schedule_config)

        if "max_runs" in schedule:
            task.max_runs = schedule["max_runs"]

        needs_reschedule = True

    # Update is_active
    if "is_active" in body:
        was_active = task.is_active
        task.is_active = body["is_active"]
        if was_active != task.is_active:
            needs_reschedule = True

    db.commit()
    db.refresh(task)

    # Reschedule if needed
    if needs_reschedule:
        try:
            unschedule_task(task.id)
            if task.is_active:
                schedule_config = json.loads(task.schedule_config) if isinstance(task.schedule_config, str) else {}
                schedule_task(task.id, task.schedule_type, schedule_config)
        except Exception as e:
            logger.log_tool_execution(
                user=current_user.username,
                tool_name="task_update",
                parameters={"task_id": task.id},
                source="api",
                success=False,
                error=f"Updated but rescheduling failed: {e}"
            )
            raise HTTPException(
                status_code=500,
                detail=f"Task updated but rescheduling failed: {str(e)}"
            )

    logger.log_tool_execution(
        user=current_user.username,
        tool_name="task_update",
        parameters={"task_id": task.id, "task_name": task.name},
        source="api",
        success=True,
        result_preview=f"Updated (active={task.is_active})"
    )

    return _serialize_task(task)


@router.delete("/{task_id}")
def delete_task(
        task_id: int,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    """Delete a task and unschedule it."""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task_name = task.name

    # Unschedule first
    try:
        unschedule_task(task.id)
    except Exception:
        pass  # Best-effort unschedule

    # Delete associated runs
    db.query(TaskRun).filter(TaskRun.task_id == task_id).delete()

    db.delete(task)
    db.commit()

    logger.log_tool_execution(
        user=current_user.username,
        tool_name="task_delete",
        parameters={"task_id": task_id, "task_name": task_name},
        source="api",
        success=True,
        result_preview="Deleted"
    )

    return {"success": True, "message": f"Task '{task_name}' deleted"}


# ---------------------------------------------------------------------------
# Task runs / execution history
# ---------------------------------------------------------------------------

@router.get("/{task_id}/runs")
def get_task_runs(
        task_id: int,
        limit: int = 20,
        offset: int = 0,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    """Get execution history for a task."""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    runs = (
        db.query(TaskRun)
        .filter(TaskRun.task_id == task_id)
        .order_by(TaskRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [_serialize_run(r) for r in runs]


# ---------------------------------------------------------------------------
# Manual trigger
# ---------------------------------------------------------------------------

@router.post("/{task_id}/run-now")
def run_task_now(
        task_id: int,
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
):
    """Manually trigger a task to run immediately in a background thread."""
    task = db.query(Task).filter(
        Task.id == task_id,
        Task.user_id == current_user.id
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    import threading
    from logic.scheduler import _run_task

    thread = threading.Thread(target=_run_task, args=(task_id, True), daemon=True)
    thread.start()

    logger.log_tool_execution(
        user=current_user.username,
        tool_name="task_run_now",
        parameters={"task_id": task_id, "task_name": task.name},
        source="api",
        success=True,
        result_preview="Triggered manually"
    )

    return {"success": True, "message": "Task triggered"}
