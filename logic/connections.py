"""
Connection handlers for external data stores and bot integrations.

Supports:
- MongoDB: Push tool outputs / reports to a MongoDB collection
- Elasticsearch: Index tool outputs / reports
- Telegram: Send messages via bot API
"""

import json
import requests
from typing import Optional, Dict, Any
from logger import get_logger

logger = get_logger()


class ConnectionError(Exception):
    """Raised when a connection operation fails."""
    pass


class MongoDBHandler:
    """Handle MongoDB connections and data pushing."""

    @staticmethod
    def test_connection(config: Dict[str, Any]) -> bool:
        try:
            from pymongo import MongoClient
            client = MongoClient(
                config.get("uri", "mongodb://localhost:27017"),
                serverSelectionTimeoutMS=5000
            )
            client.server_info()
            client.close()
            return True
        except Exception:
            return False

    @staticmethod
    def push_data(config: Dict[str, Any], data: Dict[str, Any], metadata: Optional[Dict] = None) -> Dict:
        try:
            from pymongo import MongoClient
            from datetime import datetime, timezone

            client = MongoClient(
                config.get("uri", "mongodb://localhost:27017"),
                serverSelectionTimeoutMS=10000
            )
            db = client[config.get("database", "scapyfy")]
            collection = db[config.get("collection", "outputs")]

            document = {
                "data": data,
                "metadata": metadata or {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "scapyfy"
            }

            result = collection.insert_one(document)
            client.close()

            return {
                "success": True,
                "inserted_id": str(result.inserted_id),
                "message": f"Data pushed to {config.get('database')}.{config.get('collection')}"
            }
        except ImportError:
            raise ConnectionError("pymongo is not installed. Install with: pip install pymongo")
        except Exception as e:
            raise ConnectionError(f"MongoDB push failed: {e}")


class ElasticsearchHandler:
    """Handle Elasticsearch connections and data indexing."""

    @staticmethod
    def test_connection(config: Dict[str, Any]) -> bool:
        try:
            url = config.get("url", "http://localhost:9200").rstrip("/")
            auth = None
            if config.get("username") and config.get("password"):
                auth = (config["username"], config["password"])

            resp = requests.get(url, auth=auth, timeout=5, verify=config.get("verify_ssl", True))
            return resp.status_code == 200
        except Exception:
            return False

    @staticmethod
    def push_data(config: Dict[str, Any], data: Dict[str, Any], metadata: Optional[Dict] = None) -> Dict:
        try:
            from datetime import datetime, timezone

            url = config.get("url", "http://localhost:9200").rstrip("/")
            index = config.get("index", "scapyfy-outputs")
            auth = None
            if config.get("username") and config.get("password"):
                auth = (config["username"], config["password"])

            document = {
                "data": data,
                "metadata": metadata or {},
                "@timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "scapyfy"
            }

            resp = requests.post(
                f"{url}/{index}/_doc",
                json=document,
                auth=auth,
                timeout=10,
                verify=config.get("verify_ssl", True)
            )

            if resp.status_code in (200, 201):
                result = resp.json()
                return {
                    "success": True,
                    "doc_id": result.get("_id", ""),
                    "message": f"Data indexed in {index}"
                }
            else:
                raise ConnectionError(f"Elasticsearch returned {resp.status_code}: {resp.text}")
        except ConnectionError:
            raise
        except Exception as e:
            raise ConnectionError(f"Elasticsearch push failed: {e}")


class TelegramHandler:
    """Handle Telegram bot interactions."""

    @staticmethod
    def test_connection(config: Dict[str, Any]) -> bool:
        try:
            token = config.get("bot_token", "")
            resp = requests.get(
                f"https://api.telegram.org/bot{token}/getMe",
                timeout=5
            )
            is_ok = resp.status_code == 200 and resp.json().get("ok", False)
            if is_ok:
                # Register bot commands menu so suggestions appear in the app
                commands = {
                    "commands": [
                        {"command": "start", "description": "Open the interactive Scapyfy menu"},
                        {"command": "menu", "description": "Show all available tools"},
                        {"command": "cancel", "description": "Cancel the current tool parameter wizard"}
                    ]
                }
                requests.post(
                    f"https://api.telegram.org/bot{token}/setMyCommands",
                    json=commands,
                    timeout=5
                )
            return is_ok
        except Exception:
            return False

    @staticmethod
    def send_message(config: Dict[str, Any], chat_id: str, text: str, parse_mode: str = "Markdown") -> Dict:
        try:
            token = config.get("bot_token", "")

            # Truncate long messages (Telegram limit is 4096)
            if len(text) > 4000:
                text = text[:4000] + "\n\n... [truncated]"

            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode
                },
                timeout=10
            )

            if resp.status_code == 200 and resp.json().get("ok"):
                return {"success": True, "message": "Message sent to Telegram"}
            else:
                # Retry without parse mode in case of formatting issues
                resp2 = requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": text},
                    timeout=10
                )
                if resp2.status_code == 200 and resp2.json().get("ok"):
                    return {"success": True, "message": "Message sent to Telegram (plain text)"}
                raise ConnectionError(f"Telegram API error: {resp.text}")
        except ConnectionError:
            raise
        except Exception as e:
            raise ConnectionError(f"Telegram send failed: {e}")

    @staticmethod
    def push_data(config: Dict[str, Any], data: Dict[str, Any], metadata: Optional[Dict] = None) -> Dict:
        """Format data and send to all bound chat IDs."""
        chat_ids = config.get("chat_ids", [])
        if not chat_ids:
            raise ConnectionError("No Telegram chat IDs configured. Users must authenticate first.")

        source = (metadata or {}).get("source", "unknown")
        tool_name = (metadata or {}).get("tool_name", "")

        # Format the message
        lines = [f"📊 *Scapyfy Report*"]
        if tool_name:
            lines.append(f"🔧 Tool: `{tool_name}`")
        if source:
            lines.append(f"📌 Source: {source}")
        lines.append("")

        # Render the output
        if source == "chat" and "text" in data and len(data) == 1:
            # If it's just chat text, render it directly without JSON wrapping
            content = data["text"]
            if len(content) > 3000:
                content = content[:3000] + "\n..."
            lines.append(content)
        else:
            # Flatten the data into readable text
            data_str = json.dumps(data, indent=2, default=str)
            if len(data_str) > 3000:
                data_str = data_str[:3000] + "\n..."
            lines.append(f"```json\n{data_str}\n```")

        text = "\n".join(lines)
        results = []
        for chat_id in chat_ids:
            try:
                result = TelegramHandler.send_message(config, str(chat_id), text)
                results.append(result)
            except Exception as e:
                results.append({"success": False, "error": str(e), "chat_id": chat_id})

        successes = sum(1 for r in results if r.get("success"))
        return {
            "success": successes > 0,
            "message": f"Sent to {successes}/{len(chat_ids)} Telegram chats"
        }

BOT_STATE = {}  # chat_id -> dict state

def poll_telegram_updates():
    """Poll Telegram API for updates to process account binding hashes."""
    from database import SessionLocal
    from models import Connection, BotAuth
    from logic.network_tools import TOOL_MAP
    
    db = SessionLocal()
    try:
        conns = db.query(Connection).filter(Connection.conn_type == "telegram", Connection.is_active == True).all()
        for conn in conns:
            try:
                config = json.loads(conn.config) if isinstance(conn.config, str) else conn.config
                token = config.get("bot_token")
                if not token:
                    continue
                
                offset = config.get("last_update_id", 0)
                resp = requests.get(f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=5", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    if not data.get("ok"):
                        continue
                        
                    updates = data.get("result", [])
                    max_update_id = offset
                    
                    config_changed = False
                    for update in updates:
                        update_id = update.get("update_id")
                        if update_id is not None and update_id >= max_update_id:
                            max_update_id = update_id + 1
                            config_changed = True
                            
                        # Handle button clicks
                        callback_query = update.get("callback_query")
                        if callback_query:
                            chat_id = str(callback_query.get("message", {}).get("chat", {}).get("id", ""))
                            data = callback_query.get("data", "")
                            requests.post(f"https://api.telegram.org/bot{token}/answerCallbackQuery", json={"callback_query_id": callback_query.get("id")}, timeout=5)
                            
                            if chat_id in config.get("chat_ids", []):
                                if data.startswith("tool_"):
                                    tool_name = data.split("_", 1)[1]
                                    from routers.tools import list_tools
                                    # Create dummy user object for list_tools
                                    from models import User
                                    dummy_user = User(username="telegram_user")
                                    tools_info = list_tools(current_user=dummy_user)
                                    tool_def = next((t for t in tools_info if t["name"] == tool_name), None)
                                    
                                    if tool_def:
                                        BOT_STATE[chat_id] = {
                                            "type": "wizard",
                                            "tool_name": tool_name,
                                            "params": {},
                                            "missing": list(tool_def["parameters"])
                                        }
                                        
                                        param = tool_def["parameters"][0]
                                        msg = f"🔧 **{tool_name} Wizard**\n\nPlease enter `{param['name']}`:\n_{param['description']}_"
                                        if not param.get("required"):
                                            msg += f"\n\n👉 Type `/skip` to use default: `{param.get('default')}`"
                                            
                                        TelegramHandler.send_message(config, chat_id, msg, parse_mode="Markdown")
                                    else:
                                        TelegramHandler.send_message(config, chat_id, f"❌ Tool definition not found for {tool_name}")
                                        
                                elif data == "agent_prompt":
                                    BOT_STATE[chat_id] = {"type": "agent"}
                                    TelegramHandler.send_message(config, chat_id, "🤖 Please type your prompt for the AI agent.")
                            continue
                            
                        message = update.get("message", {})
                        text = message.get("text", "").strip()
                        chat_id = str(message.get("chat", {}).get("id", ""))
                        
                        if text and chat_id:
                            # Check if it's a binding hash
                            bot_auth = db.query(BotAuth).filter(BotAuth.auth_hash == text, BotAuth.connection_id == conn.id).first()
                            if bot_auth and not bot_auth.is_bound:
                                bot_auth.is_bound = True
                                bot_auth.external_user_id = chat_id
                                
                                chat_ids = config.setdefault("chat_ids", [])
                                if chat_id not in chat_ids:
                                    chat_ids.append(chat_id)
                                
                                conn.config = json.dumps(config)
                                db.commit()
                                
                                TelegramHandler.send_message(config, chat_id, "✅ Account successfully bound to Scapyfy!\n\nType /menu or /start to see available commands.")
                                logger.log_app_event("account_bound", {"message": f"Bound Telegram chat {chat_id} to connection '{conn.name}' via polling"})
                                continue
                            
                            # If already bound, process commands and agent prompts
                            if chat_id in config.get("chat_ids", []):
                                if text in ["/start", "/menu", "/help"]:
                                    BOT_STATE.pop(chat_id, None)  # Reset state
                                    from routers.tools import list_tools
                                    from models import User
                                    tools_info = list_tools(current_user=User(username="telegram_user"))
                                    
                                    keyboard_buttons = []
                                    row = []
                                    for t in tools_info:
                                        row.append({"text": f"🛠️ {t['name'].replace('_', ' ').title()}", "callback_data": f"tool_{t['name']}"})
                                        if len(row) == 2:
                                            keyboard_buttons.append(row)
                                            row = []
                                    if row:
                                        keyboard_buttons.append(row)
                                        
                                    keyboard_buttons.append([{"text": "🤖 Ask AI Agent", "callback_data": "agent_prompt"}])
                                    keyboard = {"inline_keyboard": keyboard_buttons}
                                    
                                    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                                        "chat_id": chat_id,
                                        "text": "🧙‍♂️ **Scapyfy Bot Menu**\nSelect a tool to run directly, or ask the agent:",
                                        "parse_mode": "Markdown",
                                        "reply_markup": keyboard
                                    }, timeout=5)
                                    
                                elif text == "/cancel":
                                    BOT_STATE.pop(chat_id, None)
                                    TelegramHandler.send_message(config, chat_id, "🚫 Operation cancelled. Type /menu to start over.")
                                    
                                else:
                                    state = BOT_STATE.get(chat_id, {})
                                    
                                    if state.get("type") == "wizard":
                                        missing = state["missing"]
                                        current_param = missing[0]
                                        
                                        if text.lower() == "/skip" and not current_param.get("required"):
                                            if "default" in current_param:
                                                state["params"][current_param["name"]] = current_param["default"]
                                        else:
                                            # Type conversion
                                            val = text
                                            if current_param.get("type") == "integer":
                                                try:
                                                    val = int(val)
                                                except ValueError:
                                                    TelegramHandler.send_message(config, chat_id, f"❌ Invalid integer. Please enter `{current_param['name']}` again:", parse_mode="Markdown")
                                                    continue
                                            elif current_param.get("type") == "boolean":
                                                val = val.lower() in ("true", "yes", "1", "y")
                                                
                                            state["params"][current_param["name"]] = val
                                            
                                        # Pop the processed parameter
                                        missing.pop(0)
                                        
                                        if not missing:
                                            # All parameters collected! Run the tool.
                                            tool_name = state["tool_name"]
                                            params = state["params"]
                                            BOT_STATE.pop(chat_id, None)
                                            
                                            params_str = ", ".join([f"{k}={v}" for k, v in params.items()])
                                            TelegramHandler.send_message(config, chat_id, f"⚙️ Running `{tool_name}` with parameters:\n`{params_str}`\n\nPlease wait...", parse_mode="Markdown")
                                            
                                            try:
                                                from logic.network_tools import TOOL_MAP
                                                if tool_name in TOOL_MAP:
                                                    result = TOOL_MAP[tool_name](**params)
                                                    if isinstance(result, dict) and "raw_output" in result:
                                                        result = result["raw_output"]
                                                    elif isinstance(result, dict):
                                                        result = json.dumps(result, indent=2)
                                                    
                                                    result = str(result)
                                                    if len(result) > 3500:
                                                        result = result[:3500] + "\n...[truncated]"
                                                    TelegramHandler.send_message(config, chat_id, f"✅ **Result:**\n```\n{result}\n```", parse_mode="Markdown")
                                                else:
                                                    TelegramHandler.send_message(config, chat_id, f"❌ Unknown tool: {tool_name}")
                                            except Exception as e:
                                                TelegramHandler.send_message(config, chat_id, f"❌ Tool Error: {str(e)}")
                                        else:
                                            # Ask for next parameter
                                            next_param = missing[0]
                                            msg = f"Please enter `{next_param['name']}`:\n_{next_param['description']}_"
                                            if not next_param.get("required"):
                                                msg += f"\n\n👉 Type `/skip` to use default: `{next_param.get('default')}`"
                                            TelegramHandler.send_message(config, chat_id, msg, parse_mode="Markdown")
                                            
                                    elif state.get("type") == "agent":
                                        # Explicit agent prompt
                                        BOT_STATE.pop(chat_id, None)
                                        TelegramHandler.send_message(config, chat_id, "⏳ _Processing with Agent..._", parse_mode="Markdown")
                                        try:
                                            from logic.loop import llm_crafter
                                            from models import User
                                            
                                            username = "telegram_user"
                                            auth = db.query(BotAuth).filter(BotAuth.external_user_id == chat_id, BotAuth.connection_id == conn.id).first()
                                            if auth:
                                                u = db.query(User).filter(User.id == auth.user_id).first()
                                                if u: username = u.username
                                                
                                            reply = llm_crafter(text, user=username)
                                            TelegramHandler.send_message(config, chat_id, reply)
                                        except Exception as e:
                                            TelegramHandler.send_message(config, chat_id, f"❌ Agent Error: {str(e)}")
                                            
                                    else:
                                        # Default (no state) - ignore or instruct user
                                        TelegramHandler.send_message(config, chat_id, "ℹ️ Please use /menu to select a tool, or click 'Ask AI Agent' to talk to the AI.")
                                        
                    if config_changed and max_update_id > offset:
                        config["last_update_id"] = max_update_id
                        conn.config = json.dumps(config)
                        db.commit()
            except Exception as e:
                pass
    finally:
        db.close()





# Handler registry
CONNECTION_HANDLERS = {
    "mongodb": MongoDBHandler,
    "elasticsearch": ElasticsearchHandler,
    "telegram": TelegramHandler,
}


def get_handler(conn_type: str):
    """Get the appropriate handler for a connection type."""
    handler = CONNECTION_HANDLERS.get(conn_type)
    if not handler:
        raise ConnectionError(f"Unknown connection type: {conn_type}")
    return handler


def test_connection(conn_type: str, config: Dict[str, Any]) -> bool:
    """Test if a connection is reachable."""
    handler = get_handler(conn_type)
    return handler.test_connection(config)


def push_to_connection(conn_type: str, config: Dict[str, Any], data: Dict[str, Any],
                       metadata: Optional[Dict] = None) -> Dict:
    """Push data to an external connection."""
    handler = get_handler(conn_type)
    return handler.push_data(config, data, metadata)
