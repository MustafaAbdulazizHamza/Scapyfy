from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from logic import network_tools
from models import User
from oauth2 import get_current_active_user
from logger import get_logger

router = APIRouter(
    prefix="/tools",
    tags=["network-tools"],
    dependencies=[Depends(get_current_active_user)]
)

logger = get_logger()


class PingRequest(BaseModel):
    target: str
    count: int = 4
    timeout: int = 5
    arguments: Optional[str] = None


class PingResponse(BaseModel):
    success: bool
    target: str
    packets_sent: int
    packets_received: int
    packet_loss: float
    rtt_min: Optional[float] = None
    rtt_avg: Optional[float] = None
    rtt_max: Optional[float] = None
    raw_output: str


class NmapRequest(BaseModel):
    target: str
    scan_type: str = "quick"
    ports: Optional[str] = None
    arguments: Optional[str] = None


class NmapResponse(BaseModel):
    success: bool
    target: str
    scan_type: str
    open_ports: List[dict]
    raw_output: str


class TracerouteRequest(BaseModel):
    target: str
    max_hops: int = 30
    timeout: int = 5
    arguments: Optional[str] = None


class TracerouteResponse(BaseModel):
    success: bool
    target: str
    hops: List[dict]
    raw_output: str


class DNSLookupRequest(BaseModel):
    target: str
    record_type: str = "A"


class DNSLookupResponse(BaseModel):
    success: bool
    target: str
    record_type: str
    records: List[str]
    raw_output: str


@router.post("/ping", response_model=PingResponse)
def ping_target(
        request: PingRequest,
        current_user: User = Depends(get_current_active_user)
):
    try:
        result = network_tools.ping(
            target=request.target,
            count=request.count,
            timeout=request.timeout,
            arguments=request.arguments
        )
        return PingResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ping failed: {str(e)}")


@router.post("/nmap", response_model=NmapResponse)
def nmap_scan_endpoint(
        request: NmapRequest,
        current_user: User = Depends(get_current_active_user)
):
    try:
        result = network_tools.nmap_scan_direct(
            target=request.target,
            scan_type=request.scan_type,
            ports=request.ports,
            arguments=request.arguments
        )
        return NmapResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Nmap scan failed: {str(e)}")


@router.post("/traceroute", response_model=TracerouteResponse)
def traceroute_target(
        request: TracerouteRequest,
        current_user: User = Depends(get_current_active_user)
):
    try:
        result = network_tools.traceroute(
            target=request.target,
            max_hops=request.max_hops,
            timeout=request.timeout,
            arguments=request.arguments
        )
        return TracerouteResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Traceroute failed: {str(e)}")


@router.post("/dns", response_model=DNSLookupResponse)
def dns_lookup(
        request: DNSLookupRequest,
        current_user: User = Depends(get_current_active_user)
):
    try:
        result = network_tools.dns_lookup(
            target=request.target,
            record_type=request.record_type
        )
        return DNSLookupResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DNS lookup failed: {str(e)}")


@router.get("/status")
def tools_status(current_user: User = Depends(get_current_active_user)):
    return {
        "nmap_available": network_tools.check_nmap_available(),
        "tools": ["ping", "nmap", "traceroute", "dns", "send_packet", "quick_port_scan", "arp_scan", "hping3", "unicornscan"],
        "user": current_user.username
    }


@router.get("/list")
def list_tools(current_user: User = Depends(get_current_active_user)):
    return [
        {
            "name": "ping_host",
            "description": "Ping a host to check if it's reachable",
            "parameters": [
                {"name": "target", "type": "string", "required": True, "description": "IP address or hostname to ping"},
                {"name": "count", "type": "integer", "required": False, "default": 4, "description": "Number of ping requests"},
                {"name": "timeout", "type": "integer", "required": False, "default": 2, "description": "Timeout in seconds"},
                {"name": "arguments", "type": "string", "required": False, "description": "Additional ping arguments (e.g. '-s 1000')"}
            ],
            "example_usage": {"target": "8.8.8.8", "count": 4, "timeout": 2, "arguments": "-s 1000"}
        },
        {
            "name": "nmap_scan",
            "description": "Perform an NMAP scan on a target",
            "parameters": [
                {"name": "target", "type": "string", "required": True, "description": "IP address, hostname, or CIDR range"},
                {"name": "scan_type", "type": "string", "required": False, "default": "basic", "description": "Scan type", "enum": ["basic", "quick", "intense", "ping", "version", "os"]},
                {"name": "ports", "type": "string", "required": False, "description": "Ports to scan (e.g., '22,80,443' or '1-1000')"},
                {"name": "arguments", "type": "string", "required": False, "description": "Additional NMAP arguments (e.g., '-Pn --open -v')"}
            ],
            "example_usage": {"target": "192.168.1.1", "scan_type": "quick", "ports": "22,80,443", "arguments": "-Pn"}
        },
        {
            "name": "traceroute_host",
            "description": "Perform a traceroute to discover the path to a target",
            "parameters": [
                {"name": "target", "type": "string", "required": True, "description": "IP address or hostname to trace"},
                {"name": "max_hops", "type": "integer", "required": False, "default": 30, "description": "Maximum number of hops"},
                {"name": "use_scapy", "type": "boolean", "required": False, "default": False, "description": "Use Scapy traceroute instead of system command"},
                {"name": "arguments", "type": "string", "required": False, "description": "Additional traceroute arguments"}
            ],
            "example_usage": {"target": "google.com", "max_hops": 30, "use_scapy": False}
        },
        {
            "name": "quick_port_scan",
            "description": "Perform a quick TCP port scan using Scapy",
            "parameters": [
                {"name": "target", "type": "string", "required": True, "description": "IP address to scan"},
                {"name": "ports", "type": "string", "required": False, "default": "22,80,443,8080,8443", "description": "Comma-separated list of ports"}
            ],
            "example_usage": {"target": "192.168.1.1", "ports": "22,80,443,8080,8443"}
        },
        {
            "name": "arp_scan",
            "description": "Perform an ARP scan to discover hosts on the local network",
            "parameters": [
                {"name": "network", "type": "string", "required": False, "default": "192.168.1.0/24", "description": "Network range in CIDR notation"}
            ],
            "example_usage": {"network": "192.168.1.0/24"}
        },
        {
            "name": "send_packet",
            "description": "Send a crafted packet using Scapy",
            "parameters": [
                {"name": "pkt_desc", "type": "string", "required": True, "description": "JSON string describing packet layers"},
                {"name": "is_ethernet", "type": "boolean", "required": False, "default": False, "description": "Use Ethernet layer (srp)"},
                {"name": "want_response", "type": "boolean", "required": False, "default": True, "description": "Wait for response"}
            ],
            "example_usage": {"pkt_desc": "{\"IP\": {\"dst\": \"8.8.8.8\"}, \"ICMP\": {}}", "is_ethernet": False, "want_response": True}
        },
        {
            "name": "hping3_probe",
            "description": "Use hping3 for advanced packet probing",
            "parameters": [
                {"name": "target", "type": "string", "required": True, "description": "IP address or hostname to probe"},
                {"name": "mode", "type": "string", "required": False, "default": "syn", "description": "Probe mode", "enum": ["syn", "ack", "fin", "udp", "icmp", "rawip"]},
                {"name": "port", "type": "integer", "required": False, "default": 80, "description": "Target port (1-65535)"},
                {"name": "count", "type": "integer", "required": False, "default": 4, "description": "Number of packets (1-100)"},
                {"name": "flags", "type": "string", "required": False, "description": "Custom TCP flags: S(YN), A(CK), F(IN), R(ST), U(RG), P(SH)"},
                {"name": "arguments", "type": "string", "required": False, "description": "Additional CLI args (e.g., '-i u1000 --ttl 64 --data 100')"}
            ],
            "example_usage": {"target": "192.168.1.1", "mode": "syn", "port": 80, "count": 4, "arguments": "-i u1000"}
        },
        {
            "name": "dns_lookup_tool",
            "description": "Perform DNS lookups for various record types",
            "parameters": [
                {"name": "target", "type": "string", "required": True, "description": "Domain name to query"},
                {"name": "record_types", "type": "string", "required": False, "default": "A", "description": "Comma-separated record types (A, AAAA, MX, NS, TXT, SOA, CNAME, PTR, SRV, CAA)"},
                {"name": "nameserver", "type": "string", "required": False, "description": "DNS server to use (e.g., '8.8.8.8')"}
            ],
            "example_usage": {"target": "google.com", "record_types": "A,MX,NS,TXT", "nameserver": "8.8.8.8"}
        }
    ]


TOOLS_DICT = {
    "ping_host": 0, "nmap_scan": 1, "traceroute_host": 2, "quick_port_scan": 3,
    "arp_scan": 4, "send_packet": 5, "hping3_probe": 6, "dns_lookup_tool": 7
}


@router.get("/{tool_name}")
def get_tool_info(tool_name: str, current_user: User = Depends(get_current_active_user)):
    if tool_name not in TOOLS_DICT:
        raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
    tools = list_tools(current_user)
    return tools[TOOLS_DICT[tool_name]]


class ExecuteToolRequest(BaseModel):
    tool_name: str
    parameters: dict

class ToolExecution(BaseModel):
    """Represents a single tool execution for context"""
    tool_name: str
    parameters: dict
    result: dict
    timestamp: Optional[str] = None


class ExplainRequest(BaseModel):
    tool_name: str  # Current tool being asked about
    parameters: dict
    result: dict
    provider: Optional[str] = None
    question: Optional[str] = None  # User's question
    conversation_history: Optional[List[dict]] = None  # Recent messages
    all_tool_executions: Optional[List[ToolExecution]] = None  # All tools run in session
    memory_summary: Optional[str] = None  # LLM summary of older conversation
    needs_summarization: Optional[bool] = False  # Request to summarize conversation


@router.post("/execute")
def execute_tool(
        request: ExecuteToolRequest,
        current_user: User = Depends(get_current_active_user)
):
    tool_map = {
        "ping_host": lambda p: network_tools.ping(p.get("target"), p.get("count", 4), p.get("timeout", 5), p.get("arguments")),
        "nmap_scan": lambda p: network_tools.nmap_scan_direct(p.get("target"), p.get("scan_type", "quick"), p.get("ports"), p.get("arguments")),
        "traceroute_host": lambda p: network_tools.traceroute(p.get("target"), p.get("max_hops", 30), p.get("timeout", 5), p.get("arguments")) if not p.get("use_scapy", False) else network_tools.traceroute(p.get("target"), p.get("max_hops", 30), p.get("timeout", 5)),
        "quick_port_scan": lambda p: {"success": True, "result": network_tools.quick_port_scan.func(p.get("target"), p.get("ports", "22,80,443,8080,8443"))},
        "arp_scan": lambda p: {"success": True, "result": network_tools.arp_scan.func(p.get("network", "192.168.1.0/24"))},
        "send_packet": lambda p: {"success": True, "result": network_tools.send_packet.func(p.get("pkt_desc"), p.get("is_ethernet", False), p.get("want_response", True))},
        "hping3_probe": lambda p: {"success": True, "result": network_tools.hping3_probe.func(p.get("target"), p.get("mode", "syn"), p.get("port", 80), p.get("count", 4), p.get("flags"), p.get("arguments"))},
        "dns_lookup_tool": lambda p: {"success": True, "result": network_tools.dns_lookup_tool.func(p.get("target"), p.get("record_types", "A"), p.get("nameserver"))},
    }
    
    if request.tool_name not in tool_map:
        logger.log_tool_execution(
            user=current_user.username,
            tool_name=request.tool_name,
            parameters=request.parameters,
            source="direct",
            success=False,
            error="Tool not found"
        )
        raise HTTPException(status_code=404, detail=f"Tool '{request.tool_name}' not found")
    
    try:
        result = tool_map[request.tool_name](request.parameters)
        
        result_preview = None
        if isinstance(result, dict):
            result_preview = result.get("result", str(result))[:200] if result.get("result") else str(result)[:200]
        
        logger.log_tool_execution(
            user=current_user.username,
            tool_name=request.tool_name,
            parameters=request.parameters,
            source="direct",
            success=True,
            result_preview=result_preview
        )
        
        return {"success": True, "tool": request.tool_name, "result": result}
    except Exception as e:
        logger.log_tool_execution(
            user=current_user.username,
            tool_name=request.tool_name,
            parameters=request.parameters,
            source="direct",
            success=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {str(e)}")


@router.post("/explain")
def explain_tool_output(
        request: ExplainRequest,
        current_user: User = Depends(get_current_active_user)
):
    """
    Use LLM to generate explanations of tool output with multi-tool context and memory.
    Supports:
    - Multiple tool executions as context
    - Persistent conversation across tool switches
    - Memory summarization for long conversations
    """
    from logic.llm_providers import LLMProviderFactory
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
    import json
    
    tool_descriptions = {
        "ping_host": "ICMP echo request/response test for network connectivity",
        "nmap_scan": "Network port and service scanner using NMAP",
        "traceroute_host": "Network path discovery showing router hops to destination",
        "quick_port_scan": "Fast TCP port scanner using Scapy SYN packets",
        "arp_scan": "Local network host discovery using ARP protocol",
        "send_packet": "Custom network packet crafting and transmission using Scapy",
        "hping3_probe": "Advanced packet probing with TCP/UDP/ICMP using hping3",
        "dns_lookup_tool": "DNS record resolution for various record types"
    }
    
    # Get the LLM provider first (needed for potential summarization)
    try:
        provider_name = request.provider if request.provider and request.provider != 'auto' else None
        if provider_name:
            provider = LLMProviderFactory.get_provider(provider_name)
        else:
            provider = LLMProviderFactory.get_default_provider()
        llm = provider.get_chat_model()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM provider error: {str(e)}")
    
    # Handle summarization request
    if request.needs_summarization and request.conversation_history:
        return _summarize_conversation(request, llm, provider.name, current_user)
    
    # Build context from ALL tool executions in the session
    tool_context_parts = []
    
    if request.all_tool_executions:
        tool_context_parts.append("## Session Tool Execution History")
        for i, exec in enumerate(request.all_tool_executions[-5:], 1):  # Last 5 tools
            tool_desc = tool_descriptions.get(exec.tool_name, "Network tool")
            result_preview = json.dumps(exec.result, default=str)
            if len(result_preview) > 500:
                result_preview = result_preview[:500] + "... (truncated)"
            tool_context_parts.append(f"""
### Tool {i}: {exec.tool_name}
- **Description**: {tool_desc}
- **Parameters**: `{json.dumps(exec.parameters, default=str)}`
- **Result Preview**: ```{result_preview}```
""")
    
    # Current tool being asked about (with full details)
    current_tool_desc = tool_descriptions.get(request.tool_name, "Network analysis tool")
    result_str = json.dumps(request.result, indent=2, default=str)
    if len(result_str) > 3000:
        result_str = result_str[:3000] + "\n... (truncated)"
    params_str = json.dumps(request.parameters, indent=2, default=str)
    
    # Build system context
    memory_context = ""
    if request.memory_summary:
        memory_context = f"""
## Previous Conversation Summary
The following is a summary of earlier conversation (you may refer to it):
{request.memory_summary}
---
"""
    
    tool_history = "\n".join(tool_context_parts) if tool_context_parts else ""
    
    system_context = f"""You are Scapyfy Assistant, a network security expert helping users understand network tool outputs.

{memory_context}
{tool_history}

## Current Tool Output (User's Current Focus)
**Tool:** {request.tool_name}
**Description:** {current_tool_desc}

**Parameters:**
```json
{params_str}
```

**Full Output:**
```json
{result_str}
```

## Guidelines
- Be concise but thorough
- Use markdown formatting for clarity
- Explain technical terms when first used
- Provide security insights when relevant
- You remember all tools executed in this session
- If user asks about a previous tool, refer to Session Tool Execution History
- Connect findings across different tool outputs when relevant"""

    messages = [SystemMessage(content=system_context)]
    
    # Add conversation history (recent messages only - older ones are summarized)
    if request.conversation_history:
        for msg in request.conversation_history:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
    
    # Add current question or initial request
    if request.question:
        messages.append(HumanMessage(content=request.question))
    else:
        initial_prompt = """Please explain this tool's output. Include:
1. **Summary**: What happened in 1-2 sentences
2. **Key Findings**: Main observations
3. **Technical Details**: Important fields and their meaning
4. **Security Implications**: Any security-relevant observations
5. **Recommendations**: Suggested next steps

Be concise but informative."""
        messages.append(HumanMessage(content=initial_prompt))
    
    try:
        response = llm.invoke(messages)
        explanation = response.content if hasattr(response, 'content') else str(response)
        
        logger.log_tool_execution(
            user=current_user.username,
            tool_name=f"{request.tool_name}_explain",
            parameters={"original_tool": request.tool_name, "has_history": bool(request.conversation_history)},
            source="direct",
            success=True,
            result_preview=explanation[:200] if explanation else None
        )
        
        return {
            "success": True,
            "tool": request.tool_name,
            "explanation": explanation,
            "provider": provider.name,
            "is_follow_up": bool(request.question)
        }
        
    except Exception as e:
        logger.log_tool_execution(
            user=current_user.username,
            tool_name=f"{request.tool_name}_explain",
            parameters={"original_tool": request.tool_name},
            source="direct",
            success=False,
            error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to generate explanation: {str(e)}")


def _summarize_conversation(request: ExplainRequest, llm, provider_name: str, current_user) -> dict:
    """
    Summarize older parts of the conversation to reduce token usage while preserving context.
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    
    if not request.conversation_history or len(request.conversation_history) < 4:
        return {
            "success": True,
            "summary": None,
            "message": "Conversation too short to summarize"
        }
    
    # Take older messages to summarize (keep recent ones intact)
    messages_to_summarize = request.conversation_history[:-4]  # Summarize all but last 4
    
    if not messages_to_summarize:
        return {
            "success": True,
            "summary": None,
            "message": "No messages to summarize"
        }
    
    # Build conversation text to summarize
    conv_text = []
    for msg in messages_to_summarize:
        role = "User" if msg.get("role") == "user" else "Assistant"
        conv_text.append(f"{role}: {msg.get('content', '')}")
    
    conversation_str = "\n\n".join(conv_text)
    
    # Include previous summary if exists
    prev_summary = ""
    if request.memory_summary:
        prev_summary = f"\nPrevious summary to incorporate:\n{request.memory_summary}\n"
    
    summarize_prompt = f"""Summarize this conversation between a user and an AI assistant about network security tools.
Preserve:
- Key findings from tool outputs discussed
- Important security observations mentioned
- Any recommendations given
- Context needed for follow-up questions

Be concise (max 300 words) but preserve essential context.
{prev_summary}
Conversation to summarize:
---
{conversation_str}
---

Provide a cohesive summary:"""

    try:
        response = llm.invoke([
            SystemMessage(content="You are a helpful assistant that summarizes technical conversations."),
            HumanMessage(content=summarize_prompt)
        ])
        
        summary = response.content if hasattr(response, 'content') else str(response)
        
        logger.log_tool_execution(
            user=current_user.username,
            tool_name="conversation_summarize",
            parameters={"messages_summarized": len(messages_to_summarize)},
            source="direct",
            success=True,
            result_preview=summary[:200] if summary else None
        )
        
        return {
            "success": True,
            "summary": summary,
            "messages_summarized": len(messages_to_summarize),
            "provider": provider_name
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to summarize conversation"
        }
