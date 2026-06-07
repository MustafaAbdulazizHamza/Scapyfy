"""
Task Scheduler Engine for Scapyfy.

Handles scheduled execution of tool chains and prompt tasks using APScheduler.
Supports: one-time, interval, and cron scheduling.
"""

import json
import uuid
import threading
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from database import SessionLocal
from models import Task, TaskRun
from logic.network_tools import TOOL_MAP
from logic.connections import push_to_connection, ConnectionError as ConnError
from logger import get_logger

logger = get_logger()

# Global scheduler instance
_scheduler: Optional[BackgroundScheduler] = None
_lock = threading.Lock()


def get_scheduler() -> BackgroundScheduler:
    """Get or create the global scheduler instance."""
    global _scheduler
    with _lock:
        if _scheduler is None:
            _scheduler = BackgroundScheduler(
                job_defaults={
                    'coalesce': True,
                    'max_instances': 3,
                    'misfire_grace_time': 60
                }
            )
            _scheduler.start()
            
            # Start Telegram polling job
            try:
                from logic.connections import poll_telegram_updates
                _scheduler.add_job(
                    poll_telegram_updates,
                    'interval',
                    seconds=5,
                    id='telegram_poller',
                    replace_existing=True,
                    max_instances=1
                )
            except Exception as e:
                logger.log_app_event("scheduler_error", {"error": f"Failed to start pollers: {str(e)}"})
                
    return _scheduler


def shutdown_scheduler():
    """Shut down the scheduler gracefully."""
    global _scheduler
    with _lock:
        if _scheduler and _scheduler.running:
            _scheduler.shutdown(wait=False)
            _scheduler = None


def _execute_step(step: Dict, user: str, provider: Optional[str] = None) -> Dict:
    """Execute a single task step (tool call or prompt)."""
    step_type = step.get("type")
    result = {"step": step, "success": False, "output": None, "error": None}

    if step_type == "tool":
        tool_name = step.get("tool_name", "")
        parameters = step.get("parameters", {})

        if tool_name not in TOOL_MAP:
            result["error"] = f"Unknown tool: {tool_name}"
            return result

        try:
            output = TOOL_MAP[tool_name](**parameters)
            result["success"] = True
            result["output"] = output if isinstance(output, str) else str(output)
        except Exception as e:
            result["error"] = str(e)

    elif step_type == "prompt":
        prompt_text = step.get("prompt_text", "")
        if not prompt_text:
            result["error"] = "No prompt text provided"
            return result

        try:
            from logic.loop import llm_crafter
            output = llm_crafter(
                prompt_text=prompt_text,
                user=user,
                max_iterations=10,
                provider_name=provider
            )
            result["success"] = True
            result["output"] = output
        except Exception as e:
            result["error"] = f"Prompt execution failed: {e}"
    else:
        result["error"] = f"Unknown step type: {step_type}"

    return result


def _run_task(task_id: int, is_manual: bool = False):
    """Execute all steps of a task and record the results."""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return
        
        if not task.is_active and not is_manual:
            return

        # Check max_runs limit
        if task.max_runs is not None and task.run_count >= task.max_runs:
            task.is_active = False
            db.commit()
            # Remove the job from the scheduler
            scheduler = get_scheduler()
            job_id = f"task_{task_id}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
            return

        # Create a task run record
        run = TaskRun(
            task_id=task_id,
            user_id=task.user_id,
            status="running",
            started_at=datetime.now(timezone.utc)
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Parse steps
        try:
            steps = json.loads(task.steps) if isinstance(task.steps, str) else task.steps
        except json.JSONDecodeError:
            run.status = "failed"
            run.error_message = "Invalid task steps JSON"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # Get user info for the task
        from models import User
        user = db.query(User).filter(User.id == task.user_id).first()
        username = user.username if user else "system"

        # Determine provider from schedule config
        provider = None
        try:
            schedule_config = json.loads(task.schedule_config) if isinstance(task.schedule_config, str) else task.schedule_config
            provider = schedule_config.get("provider")
        except Exception:
            pass

        # Execute each step
        steps_log = []
        all_success = True
        for i, step in enumerate(steps):
            step_result = _execute_step(step, username, provider)
            step_result["step_index"] = i
            step_result["executed_at"] = datetime.now(timezone.utc).isoformat()
            steps_log.append(step_result)

            if not step_result["success"]:
                all_success = False
                # Continue to next step even on failure (don't break the chain)

        # Update run record
        run.status = "completed" if all_success else "failed"
        run.steps_log = json.dumps(steps_log, default=str)
        if not all_success:
            errors = [s["error"] for s in steps_log if s.get("error")]
            run.error_message = "; ".join(errors)
        run.completed_at = datetime.now(timezone.utc)

        # Update task
        task.run_count += 1
        task.last_run_at = datetime.now(timezone.utc)

        # Check if max_runs reached after this run
        if task.max_runs is not None and task.run_count >= task.max_runs:
            task.is_active = False
            scheduler = get_scheduler()
            job_id = f"task_{task_id}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)

        db.commit()

        # Route output to connections
        try:
            output_conn_ids = json.loads(task.output_connections) if task.output_connections else []
        except (json.JSONDecodeError, TypeError):
            output_conn_ids = []

        if output_conn_ids:
            _route_to_connections(db, output_conn_ids, steps_log, task.name, username)

        logger.log_tool_execution(
            user=username,
            tool_name="task_execution",
            parameters={"task_id": task_id, "task_name": task.name},
            source="scheduler",
            success=all_success,
            result_preview=f"Completed {len(steps_log)} steps"
        )

    except Exception as e:
        logger.log_tool_execution(
            user="system",
            tool_name="task_execution",
            parameters={"task_id": task_id},
            source="scheduler",
            success=False,
            error=str(e)
        )
    finally:
        db.close()


def _route_to_connections(db, connection_ids: List[int], steps_log: List[Dict],
                          task_name: str, username: str):
    """Route task output to configured external connections."""
    from models import Connection

    for conn_id in connection_ids:
        try:
            conn = db.query(Connection).filter(
                Connection.id == conn_id,
                Connection.is_active == True
            ).first()

            if not conn:
                continue

            config = json.loads(conn.config) if isinstance(conn.config, str) else conn.config

            data = {
                "task_name": task_name,
                "user": username,
                "steps": steps_log,
                "total_steps": len(steps_log),
                "successful_steps": sum(1 for s in steps_log if s.get("success")),
            }

            metadata = {
                "source": "task",
                "task_name": task_name,
                "tool_name": f"Task: {task_name}",
            }

            push_to_connection(conn.conn_type, config, data, metadata)

        except ConnError as e:
            logger.log_tool_execution(
                user=username,
                tool_name="output_routing",
                parameters={"connection_id": conn_id},
                source="scheduler",
                success=False,
                error=str(e)
            )
        except Exception as e:
            pass


def schedule_task(task_id: int, schedule_type: str, schedule_config: Dict[str, Any]):
    """Add or update a task in the scheduler."""
    scheduler = get_scheduler()
    job_id = f"task_{task_id}"

    # Remove existing job if any
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    if schedule_type == "once":
        run_at_str = schedule_config.get("run_at")
        if not run_at_str:
            raise ValueError("'run_at' is required for 'once' schedule type")

        run_at = datetime.fromisoformat(run_at_str)
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)

        trigger = DateTrigger(run_date=run_at)

    elif schedule_type == "interval":
        seconds = schedule_config.get("interval_seconds", 3600)
        trigger = IntervalTrigger(seconds=seconds)

    elif schedule_type == "cron":
        cron_expr = schedule_config.get("cron_expression", "")
        if not cron_expr:
            raise ValueError("'cron_expression' is required for 'cron' schedule type")

        parts = cron_expr.strip().split()
        if len(parts) != 5:
            raise ValueError("Cron expression must have 5 fields: minute hour day month day_of_week")

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4]
        )
    else:
        raise ValueError(f"Unknown schedule type: {schedule_type}")

    scheduler.add_job(
        _run_task,
        trigger=trigger,
        args=[task_id],
        id=job_id,
        name=f"Task {task_id}",
        replace_existing=True
    )


def unschedule_task(task_id: int):
    """Remove a task from the scheduler."""
    scheduler = get_scheduler()
    job_id = f"task_{task_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def load_active_tasks():
    """Load and schedule all active tasks from the database. Called on startup."""
    db = SessionLocal()
    try:
        tasks = db.query(Task).filter(Task.is_active == True).all()
        count = 0
        for task in tasks:
            try:
                schedule_config = json.loads(task.schedule_config) if isinstance(task.schedule_config, str) else task.schedule_config
                schedule_task(task.id, task.schedule_type, schedule_config)
                count += 1
            except Exception as e:
                print(f"⚠️  Failed to schedule task {task.id} ({task.name}): {e}")
        if count:
            print(f"📅 Loaded {count} active task(s) into scheduler")
    except Exception as e:
        print(f"❌ Error loading tasks: {e}")
    finally:
        db.close()
