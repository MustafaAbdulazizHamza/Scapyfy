import os
import json
import logging
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

LOGS_DIR = Path(os.getenv("LOGS_DIR", "logs"))
LOG_ROTATION_HOURS = int(os.getenv("LOG_ROTATION_HOURS", "24"))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "30"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

LOGS_DIR.mkdir(exist_ok=True)


class ScapyfyLogger:
    _instance: Optional['ScapyfyLogger'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.app_logger = self._create_logger("scapyfy_app", "app.log")
        self.llm_logger = self._create_logger("scapyfy_llm", "llm.log")
        self.tools_logger = self._create_logger("scapyfy_tools", "tools.log")
        self.api_logger = self._create_logger("scapyfy_api", "api.log")
        self.auth_logger = self._create_logger("scapyfy_auth", "auth.log")
    
    def _create_logger(self, name: str, filename: str) -> logging.Logger:
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        log_file = LOGS_DIR / filename
        
        handler = TimedRotatingFileHandler(
            log_file,
            when='H',
            interval=LOG_ROTATION_HOURS,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        handler.suffix = "%Y-%m-%d_%H-%M"
        handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
        
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def _format_log(self, data: dict) -> str:
        return json.dumps(data, default=str, ensure_ascii=False)
    
    def log_app_event(self, event: str, details: dict = None):
        entry = {
            "event": event,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.app_logger.info(self._format_log(entry))
    
    def log_llm_request(
        self,
        user: str,
        provider: str,
        model: str,
        prompt: str,
        session_id: str = None
    ):
        entry = {
            "type": "LLM_REQUEST",
            "user": user,
            "provider": provider,
            "model": model,
            "prompt_preview": prompt[:500] if len(prompt) > 500 else prompt,
            "prompt_length": len(prompt),
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        self.llm_logger.info(self._format_log(entry))
    
    def log_llm_response(
        self,
        user: str,
        provider: str,
        model: str,
        response_length: int,
        tool_calls: list = None,
        session_id: str = None,
        duration_ms: float = None
    ):
        entry = {
            "type": "LLM_RESPONSE",
            "user": user,
            "provider": provider,
            "model": model,
            "response_length": response_length,
            "tool_calls": tool_calls or [],
            "session_id": session_id,
            "duration_ms": duration_ms,
            "timestamp": datetime.now().isoformat()
        }
        self.llm_logger.info(self._format_log(entry))
    
    def log_llm_error(
        self,
        user: str,
        provider: str,
        model: str,
        error: str,
        session_id: str = None
    ):
        entry = {
            "type": "LLM_ERROR",
            "user": user,
            "provider": provider,
            "model": model,
            "error": str(error),
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        self.llm_logger.error(self._format_log(entry))
    
    def log_tool_execution(
        self,
        user: str,
        tool_name: str,
        parameters: dict,
        source: str,
        success: bool = True,
        result_preview: str = None,
        error: str = None,
        session_id: str = None
    ):
        entry = {
            "type": "TOOL_EXEC",
            "user": user,
            "tool": tool_name,
            "parameters": parameters,
            "source": source,
            "success": success,
            "result_preview": result_preview[:200] if result_preview and len(result_preview) > 200 else result_preview,
            "error": error,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }
        if success:
            self.tools_logger.info(self._format_log(entry))
        else:
            self.tools_logger.error(self._format_log(entry))
    
    def log_api_request(
        self,
        user: str,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float = None,
        client_ip: str = None
    ):
        entry = {
            "type": "API_REQUEST",
            "user": user,
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "client_ip": client_ip,
            "timestamp": datetime.now().isoformat()
        }
        level = logging.INFO if status_code < 400 else logging.WARNING if status_code < 500 else logging.ERROR
        self.api_logger.log(level, self._format_log(entry))
    
    def log_auth_event(
        self,
        event: str,
        user: str = None,
        success: bool = True,
        client_ip: str = None,
        details: str = None
    ):
        entry = {
            "type": f"AUTH_{event.upper()}",
            "user": user,
            "success": success,
            "client_ip": client_ip,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        if success:
            self.auth_logger.info(self._format_log(entry))
        else:
            self.auth_logger.warning(self._format_log(entry))


scapyfy_logger = ScapyfyLogger()


def get_logger() -> ScapyfyLogger:
    return scapyfy_logger
