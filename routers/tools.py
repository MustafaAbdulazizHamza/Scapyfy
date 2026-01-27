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
