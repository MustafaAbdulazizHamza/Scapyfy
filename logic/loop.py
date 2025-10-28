from dotenv import load_dotenv
import os
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from scapy.all import Ether, IP, ARP, TCP, UDP, ICMP, sr, srp, send, Packet
from scapy.packet import Raw
import json
import logging
import uuid
from datetime import datetime
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate, \
    MessagesPlaceholder
from langchain_core.runnables import RunnableSerializable
from langchain_core.messages import AIMessage, ToolMessage

current_user = ""
current_session_id = None

# Simple Logging Setup
def setup_execution_logging():
    """Setup logging for tool execution tracking."""
    logs_dir = os.path.join(os.getcwd(), 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    logger = logging.getLogger('packet_crafter_tools')
    logger.setLevel(logging.INFO)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # File handler
    file_handler = logging.FileHandler(
        os.path.join(logs_dir, 'packet_crafter_executions.log'),
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

# Initialize logger
execution_logger = setup_execution_logging()

def log_tool_execution(tool_name: str, tool_args: dict, tool_output: str, user: str, session_id: str):
    """Log tool execution details."""
    log_entry = {
        "session_id": session_id,
        "user": user,
        "tool_name": tool_name,
        "arguments": tool_args,
        "output_length": len(str(tool_output)),
        "timestamp": datetime.now().isoformat()
    }
    execution_logger.info(f"TOOL_EXEC: {json.dumps(log_entry)}")

def log_session_start(prompt: str, user: str, session_id: str):
    """Log session start."""
    log_entry = {
        "session_id": session_id,
        "user": user,
        "action": "SESSION_START",
        "prompt": prompt,
        "timestamp": datetime.now().isoformat()
    }
    execution_logger.info(f"SESSION: {json.dumps(log_entry)}")

def log_session_end(result: str, user: str, session_id: str):
    """Log session end."""
    log_entry = {
        "session_id": session_id,
        "user": user,
        "action": "SESSION_END",
        "result_length": len(result),
        "timestamp": datetime.now().isoformat()
    }
    execution_logger.info(f"SESSION: {json.dumps(log_entry)}")

load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    raise Exception("OPENAI_API_KEY not set")

@tool
def send_pkt(pkt_desc: str, isEther: bool = False, wantResp: bool = True) -> str:
    """
    Sends a crafted packet using Scapy based on a JSON-formatted string.
    Parameters:
    - pkt_desc: A JSON string describing protocol layers and their fields.
      Example: '{"Ether": {"src": "00:11:22:33:44:55"}, "IP": {"dst": "192.168.0.1"}, "TCP": {"dport": 22, "flags": "S"}}'
    - isEther: Whether the link layer (Ether) is used (srp instead of sr).
    - wantResp: Whether to return the first response packet.
    Returns:
    - The first response Packet if wantResp is True and a response is received.
    - None otherwise.
    """
    layers = json.loads(pkt_desc)
    pkt = None
    for layer_name, fields in layers.items():
        layer_cls = globals().get(layer_name)
        if not layer_cls:
            raise ValueError(f"Unknown layer: {layer_name}")
        layer = layer_cls(**fields)
        if pkt is None:
            pkt = layer
        else:
            pkt = pkt / layer
    if isEther:
        if wantResp:
            answered, _ = srp(pkt, timeout=2, verbose=0)
            try:
                return repr(answered[0][1])
            except IndexError:
                return "No answer"
        else:
            send(pkt, verbose=0)
            return "No answer"
    else:
        if wantResp:
            answered, _ = sr(pkt, timeout=2, verbose=0)
            try:
                return repr(answered[0][1])
            except IndexError:
                return "No answer"
        else:
            send(pkt, verbose=0)
            return "No answer"


@tool
def final_report(report: str) -> str:
    """
    Submit the final report
    """
    return report


llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.0)
system_prompt = SystemMessagePromptTemplate.from_template(
    "You are Prof. Packet Crafter, a network assistant in a lab environment. "
    "Craft packets using available tools based on situations, Use IP layer only unless the task explicitly requires Ethernet."
    "Write the report in plain text. If you are asked to perform passive crafting, use the final_report() tool to return only the JSON structure of the packet requested. Do NOT use other tools."
)
user_prompt = HumanMessagePromptTemplate.from_template(
    "Situation:\n'''{situation}'''"
)
prompt = ChatPromptTemplate.from_messages([
    system_prompt,
    user_prompt,
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])
tools = [send_pkt, final_report]
name2tool = {tool.name: tool.func for tool in tools}


class CustomExecutor:
    def __init__(self, max_iterations: int) -> None:
        self.max_iterations = max_iterations
        self.agent: RunnableSerializable = (
                {"situation": lambda x: x["situation"],
                 "agent_scratchpad": lambda x: x.get("agent_scratchpad")}
                | prompt
                | llm.bind_tools(tools, tool_choice="any")
        )

    def invoke(self, situation: str) -> str:
        agent_scratchpad = []
        for _ in range(self.max_iterations):
            tool_call = self.agent.invoke(
                {
                    "situation": situation,
                    "agent_scratchpad": agent_scratchpad
                }
            )
            if not tool_call.tool_calls:
                raise Exception("No tool calls from agent")
            for tool_call in tool_call.tool_calls:
                agent_scratchpad.append(AIMessage(content="", tool_calls=[tool_call]))
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_call_id = tool_call["id"]

                try:
                    tool_output = name2tool[tool_name](**tool_args)
                except Exception as e:
                    tool_output = f"Tool execution error: {e}"

                # Add logging here
                log_tool_execution(tool_name, tool_args, tool_output, current_user, current_session_id)

                agent_scratchpad.append(ToolMessage(
                    content=str(tool_output),
                    tool_call_id=tool_call_id
                ))
                if tool_name == "final_report":
                    return str(tool_output)
        raise Exception("Maximum Number of Iterations Exceeded")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass


def llm_crafter(prompt: str, user: str, max_iterations: int) -> str:
    global current_user, current_session_id
    current_user = user
    current_session_id = str(uuid.uuid4())[:8]

    # Log session start
    log_session_start(prompt, user, current_session_id)

    with CustomExecutor(max_iterations=max_iterations) as executor:
        report = executor.invoke(situation=prompt)

        # Log session end
        log_session_end(report, user, current_session_id)

        return report
