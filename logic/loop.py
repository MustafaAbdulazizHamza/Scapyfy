from dotenv import load_dotenv
import os
import json
import uuid
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from threading import local

from langchain_core.prompts import (
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    ChatPromptTemplate,
    MessagesPlaceholder,
)
from langchain_core.runnables import RunnableSerializable
from langchain_core.messages import AIMessage, ToolMessage

from logic.llm_providers import LLMProviderFactory, LLMProvider
from logic.network_tools import ALL_TOOLS_WITH_REPORT, TOOL_MAP
from logger import get_logger

load_dotenv()

_session_context = local()
logger = get_logger()


@dataclass
class SessionContext:
    user: str
    session_id: str
    provider_name: str
    model_name: str = ""


def get_session_context() -> Optional[SessionContext]:
    return getattr(_session_context, 'context', None)


def set_session_context(context: SessionContext):
    _session_context.context = context


SYSTEM_PROMPT = """You are Prof. Packet Crafter, an expert network security analyst and packet crafting assistant in a lab environment.

Your capabilities include:
1. **Packet Crafting**: Create and send custom network packets using Scapy
2. **Network Scanning**: Perform NMAP scans, port scans, and ARP discovery
3. **Network Diagnostics**: Execute ping, traceroute, DNS lookups, and hping3 probes
4. **Analysis**: Analyze responses and provide detailed reports

Guidelines:
- Use IP layer by default unless the task explicitly requires Ethernet layer
- Always validate targets and parameters before executing tools
- Provide clear, detailed reports of your findings
- For passive crafting requests, use craft_packet_json or final_report to return packet structures without sending
- Be security-conscious and educational in your explanations

Available tools:
- send_packet: Send crafted packets using Scapy
- craft_packet_json: Create packet structure without sending
- ping_host: Basic connectivity check
- traceroute_host: Path discovery
- nmap_scan: Comprehensive port/service scanning
- hping3_probe: Advanced packet probing
- quick_port_scan: Fast Scapy-based port scan
- arp_scan: Local network host discovery
- dns_lookup_tool: DNS queries (A, AAAA, MX, NS, TXT, SOA, CNAME, PTR, SRV, CAA)
- final_report: Submit your final analysis

Write all reports in plain text with clear formatting."""

system_prompt_template = SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT)
user_prompt_template = HumanMessagePromptTemplate.from_template(
    "Task:\n'''{situation}'''"
)

prompt = ChatPromptTemplate.from_messages([
    system_prompt_template,
    user_prompt_template,
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])


class AgentExecutor:
    
    def __init__(
        self,
        max_iterations: int = 10,
        provider: Optional[LLMProvider] = None,
        provider_name: Optional[str] = None
    ):
        self.max_iterations = max_iterations
        
        if provider:
            self.provider = provider
        elif provider_name:
            self.provider = LLMProviderFactory.get_provider(provider_name)
        else:
            self.provider = LLMProviderFactory.get_default_provider()
        
        self.llm = self.provider.get_chat_model()
        self.model_name = getattr(self.llm, 'model_name', getattr(self.llm, 'model', 'unknown'))
        
        self.agent: RunnableSerializable = (
            {
                "situation": lambda x: x["situation"],
                "agent_scratchpad": lambda x: x.get("agent_scratchpad", [])
            }
            | prompt
            | self.llm.bind_tools(ALL_TOOLS_WITH_REPORT, tool_choice="auto")
        )
    
    def invoke(self, situation: str, context: SessionContext) -> str:
        agent_scratchpad = []
        
        for iteration in range(self.max_iterations):
            start_time = time.time()
            try:
                response = self.agent.invoke({
                    "situation": situation,
                    "agent_scratchpad": agent_scratchpad
                })
                duration_ms = (time.time() - start_time) * 1000
            except Exception as e:
                logger.log_llm_error(
                    user=context.user,
                    provider=context.provider_name,
                    model=context.model_name,
                    error=str(e),
                    session_id=context.session_id
                )
                return f"LLM invocation error: {e}"
            
            if not response.tool_calls:
                logger.log_llm_response(
                    user=context.user,
                    provider=context.provider_name,
                    model=context.model_name,
                    response_length=len(str(response.content)) if response.content else 0,
                    tool_calls=[],
                    session_id=context.session_id,
                    duration_ms=duration_ms
                )
                if response.content:
                    return str(response.content)
                return "Agent completed without producing output"
            
            tool_call_names = [tc["name"] for tc in response.tool_calls]
            logger.log_llm_response(
                user=context.user,
                provider=context.provider_name,
                model=context.model_name,
                response_length=len(str(response.content)) if response.content else 0,
                tool_calls=tool_call_names,
                session_id=context.session_id,
                duration_ms=duration_ms
            )
            
            for tool_call in response.tool_calls:
                agent_scratchpad.append(
                    AIMessage(content="", tool_calls=[tool_call])
                )
                
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_call_id = tool_call["id"]
                
                try:
                    if tool_name in TOOL_MAP:
                        tool_output = TOOL_MAP[tool_name](**tool_args)
                        success = True
                        error = None
                    else:
                        tool_output = f"Unknown tool: {tool_name}"
                        success = False
                        error = "Unknown tool"
                except Exception as e:
                    tool_output = f"Tool execution error: {e}"
                    success = False
                    error = str(e)
                
                logger.log_tool_execution(
                    user=context.user,
                    tool_name=tool_name,
                    parameters=tool_args,
                    source="llm",
                    success=success,
                    result_preview=str(tool_output),
                    error=error,
                    session_id=context.session_id
                )
                
                agent_scratchpad.append(
                    ToolMessage(content=str(tool_output), tool_call_id=tool_call_id)
                )
                
                if tool_name == "final_report":
                    return str(tool_output)
        
        return f"Maximum iterations ({self.max_iterations}) exceeded. Partial results may be available in logs."
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        pass


def llm_crafter(
    prompt_text: str,
    user: str,
    max_iterations: int = 10,
    provider_name: Optional[str] = None
) -> str:
    context = SessionContext(
        user=user,
        session_id=str(uuid.uuid4())[:8],
        provider_name=provider_name or "auto"
    )
    set_session_context(context)
    
    try:
        executor = AgentExecutor(
            max_iterations=max_iterations,
            provider_name=provider_name
        )
        context.provider_name = executor.provider.name
        context.model_name = executor.model_name
        
        logger.log_llm_request(
            user=user,
            provider=context.provider_name,
            model=context.model_name,
            prompt=prompt_text,
            session_id=context.session_id
        )
        
        result = executor.invoke(situation=prompt_text, context=context)
        
        return result
    except Exception as e:
        logger.log_llm_error(
            user=user,
            provider=context.provider_name,
            model=context.model_name,
            error=str(e),
            session_id=context.session_id
        )
        raise RuntimeError(f"Agent execution failed: {e}") from e


def get_available_providers() -> list:
    return LLMProviderFactory.get_available_providers()
