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




def set_session_context(context: SessionContext):
    _session_context.context = context


AGENT_SYSTEM_PROMPT = """You are Prof. Packet Crafter, an expert network security analyst and packet crafting assistant in a lab environment.

Your capabilities include:
1. **Packet Crafting**: Create and send custom network packets using Scapy
2. **Network Scanning**: Perform NMAP scans, port scans, and ARP discovery
3. **Network Diagnostics**: Execute ping, traceroute, DNS lookups, and hping3 probes
4. **Analysis**: Analyze responses and provide detailed reports

Guidelines:
- Use IP layer by default unless the task explicitly requires Ethernet layer
- Always validate targets and parameters before executing tools
- Provide clear, detailed reports of your findings
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
- http_request: Send HTTP/HTTPS requests
- final_report: Submit your final analysis

CRITICAL INSTRUCTION: You MUST use the native tool calling API. If your environment does not support native tool calling, you MUST output EXACTLY ONE JSON block for your tool call:
```json
{{"name": "tool_name", "parameters": {{"arg1": "value1"}}}}
```
DO NOT output python function calls like `tool_name(arg1=value1)`.
To communicate with the user, you MUST use the final_report tool.

Write all reports in plain text with clear formatting.

{memory_context}"""

ASK_SYSTEM_PROMPT = """You are Prof. Packet Crafter, an expert network security analyst and packet crafting assistant in a lab environment.

Your capabilities include:
1. **Explanation**: Explain networking concepts, packet structures, and security principles.
2. **Passive Crafting**: Generate packet structures as JSON without executing or sending them.

Guidelines:
- Do NOT attempt to perform active network scans or send packets. You are in ASK MODE.
- When asked to craft a packet, use the craft_packet_json tool to return the packet structure.
- Provide clear, detailed, and educational explanations.
- Be security-conscious in your explanations.

Available tools:
- craft_packet_json: Create packet structure without sending
- final_report: Submit your final analysis

CRITICAL INSTRUCTION: You MUST use the native tool calling API. If your environment does not support native tool calling, you MUST output EXACTLY ONE JSON block for your tool call:
```json
{{"name": "tool_name", "parameters": {{"arg1": "value1"}}}}
```
DO NOT output python function calls like `tool_name(arg1=value1)`.
To communicate with the user, you MUST use the final_report tool.

Write all reports in plain text with clear formatting.

{memory_context}"""


class AgentExecutor:
    
    def __init__(
        self,
        max_iterations: int = 10,
        provider: Optional[LLMProvider] = None,
        provider_name: Optional[str] = None,
        memory_context: Optional[str] = None,
        mode: str = "agent"
    ):
        self.max_iterations = max_iterations
        self.memory_context = memory_context or ""
        self.mode = mode
        
        if provider:
            self.provider = provider
        elif provider_name:
            self.provider = LLMProviderFactory.get_provider(provider_name)
        else:
            self.provider = LLMProviderFactory.get_default_provider()
        
        self.llm = self.provider.get_chat_model()
        self.model_name = getattr(self.llm, 'model_name', getattr(self.llm, 'model', 'unknown'))
        
        # Format memory context for the prompt
        memory_text = ""
        if self.memory_context:
            memory_text = f"\n\n**Previous Session Context:**\n{self.memory_context}"
            
        if self.mode == "ask":
            system_prompt = ASK_SYSTEM_PROMPT
            allowed_tools = [t for t in ALL_TOOLS_WITH_REPORT if t.name in ("craft_packet_json", "final_report")]
        else:
            system_prompt = AGENT_SYSTEM_PROMPT
            allowed_tools = ALL_TOOLS_WITH_REPORT
            
        self.allowed_tools = allowed_tools
            
        prompt = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system_prompt),
            HumanMessagePromptTemplate.from_template("Task:\n'''{situation}'''"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        self.agent: RunnableSerializable = (
            {
                "situation": lambda x: x["situation"],
                "agent_scratchpad": lambda x: x.get("agent_scratchpad", []),
                "memory_context": lambda x: memory_text
            }
            | prompt
            | self.llm.bind_tools(allowed_tools, tool_choice="auto")
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
                # Fallback: attempt to parse tool call from content if it's JSON
                parsed_fallback_tools = []
                if response.content:
                    try:
                        import json
                        content_str = str(response.content).strip()
                        
                        # Try to extract JSON block using curly braces if no markdown blocks
                        if "```" in content_str:
                            if "```json" in content_str:
                                json_str = content_str.split("```json")[1].split("```")[0].strip()
                            else:
                                json_str = content_str.split("```")[1].split("```")[0].strip()
                        else:
                            # Find first { and last }
                            start = content_str.find('{')
                            end = content_str.rfind('}')
                            if start != -1 and end != -1 and end > start:
                                json_str = content_str[start:end+1]
                            else:
                                json_str = content_str
                                
                        try:
                            data = json.loads(json_str)
                        except json.JSONDecodeError:
                            import ast
                            # Sometimes LLMs output Python dictionaries with True/False instead of true/false
                            data = ast.literal_eval(json_str)
                            
                        if isinstance(data, dict) and "name" in data and ("parameters" in data or "args" in data):
                            args = data.get("parameters") or data.get("args", {})
                            parsed_fallback_tools.append({
                                "name": data["name"],
                                "args": args,
                                "id": "call_" + str(uuid.uuid4())[:8]
                            })
                    except Exception:
                        pass
                        
                if not parsed_fallback_tools and response.content:
                    import re
                    import ast
                    valid_tool_names = [t.name for t in self.allowed_tools]
                    func_pattern = re.compile(r'(\w+)\s*\((.*?)\)', re.DOTALL)
                    for match in func_pattern.finditer(str(response.content)):
                        func_name = match.group(1)
                        if func_name in valid_tool_names:
                            args_str = match.group(2)
                            try:
                                expr = ast.parse(f"dummy({args_str})", mode='eval')
                                kwargs = {}
                                for kw in expr.body.keywords:
                                    val = ast.literal_eval(kw.value)
                                    if isinstance(val, dict):
                                        import json
                                        kwargs[kw.arg] = json.dumps(val)
                                    else:
                                        kwargs[kw.arg] = val
                                parsed_fallback_tools.append({
                                    "name": func_name,
                                    "args": kwargs,
                                    "id": "call_" + str(uuid.uuid4())[:8]
                                })
                            except Exception:
                                pass
                
                if parsed_fallback_tools:
                    response.tool_calls = parsed_fallback_tools
                else:
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
    provider_name: Optional[str] = None,
    memory_context: Optional[str] = None,
    mode: str = "agent"
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
            provider_name=provider_name,
            memory_context=memory_context,
            mode=mode
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


def summarize_chat(
    messages: list,
    previous_summary: Optional[str] = None,
    provider_name: Optional[str] = None
) -> str:
    """
    Summarize chat messages into a memory context for future interactions.
    """
    if provider_name:
        provider = LLMProviderFactory.get_provider(provider_name)
    else:
        provider = LLMProviderFactory.get_default_provider()
    
    llm = provider.get_chat_model()
    
    # Build the conversation text
    conversation = ""
    for msg in messages:
        role = "User" if msg.get("type") == "user" else "Assistant"
        conversation += f"{role}: {msg.get('content', '')}\n\n"
    
    # Build the summarization prompt
    if previous_summary:
        prompt = f"""You are summarizing a chat conversation for memory purposes.

Previous context summary:
{previous_summary}

New conversation to incorporate:
{conversation}

Create a concise but comprehensive summary that:
1. Captures the key topics discussed
2. Notes any important findings, targets, or results
3. Preserves context for future related queries
4. Is written in a way that helps continue the conversation naturally

Keep the summary under 500 words. Focus on actionable information."""
    else:
        prompt = f"""You are summarizing a chat conversation for memory purposes.

Conversation:
{conversation}

Create a concise but comprehensive summary that:
1. Captures the key topics discussed
2. Notes any important findings, targets, or results  
3. Preserves context for future related queries
4. Is written in a way that helps continue the conversation naturally

Keep the summary under 500 words. Focus on actionable information."""
    
    try:
        response = llm.invoke(prompt)
        return response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        logger.log_llm_error(
            user="system",
            provider=provider.name,
            model=getattr(llm, 'model_name', 'unknown'),
            error=f"Summarization failed: {e}",
            session_id="summarize"
        )
        # Return a basic summary if LLM fails
        return f"Previous conversation with {len(messages)} messages."


def get_available_providers() -> list:
    return LLMProviderFactory.get_available_providers()
