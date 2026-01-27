from langchain.tools import tool
from scapy.all import Ether, IP, ARP, TCP, UDP, ICMP, sr, srp, send, traceroute as scapy_traceroute
from scapy.packet import Raw
import subprocess
import json
import shutil
import re
from typing import Optional


@tool
def send_packet(pkt_desc: str, is_ethernet: bool = False, want_response: bool = True) -> str:
    """
    Send a crafted packet using Scapy based on a JSON-formatted string.
    
    Args:
        pkt_desc: A JSON string describing protocol layers and their fields.
            Example: '{"IP": {"dst": "192.168.1.1"}, "TCP": {"dport": 80, "flags": "S"}}'
        is_ethernet: Whether the link layer (Ether) is used (srp instead of sr).
        want_response: Whether to wait for and return the response packet.
    
    Returns:
        The response packet representation if want_response is True, otherwise "Packet sent".
    """
    try:
        layers = json.loads(pkt_desc)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"
    
    ALLOWED_LAYERS = {
        "Ether": Ether, "IP": IP, "ARP": ARP, "TCP": TCP,
        "UDP": UDP, "ICMP": ICMP, "Raw": Raw
    }
    
    pkt = None
    for layer_name, fields in layers.items():
        if layer_name not in ALLOWED_LAYERS:
            return f"Unknown or disallowed layer: {layer_name}. Allowed: {list(ALLOWED_LAYERS.keys())}"
        
        layer_cls = ALLOWED_LAYERS[layer_name]
        try:
            layer = layer_cls(**fields)
        except Exception as e:
            return f"Error creating {layer_name} layer: {e}"
        
        if pkt is None:
            pkt = layer
        else:
            pkt = pkt / layer
    
    try:
        if is_ethernet:
            if want_response:
                answered, _ = srp(pkt, timeout=2, verbose=0)
                if answered:
                    return repr(answered[0][1])
                return "No response received"
            else:
                send(pkt, verbose=0)
                return "Packet sent successfully"
        else:
            if want_response:
                answered, _ = sr(pkt, timeout=2, verbose=0)
                if answered:
                    return repr(answered[0][1])
                return "No response received"
            else:
                send(pkt, verbose=0)
                return "Packet sent successfully"
    except Exception as e:
        return f"Error sending packet: {e}"


@tool
def craft_packet_json(pkt_desc: str) -> str:
    """
    Craft a packet structure and return it as JSON without sending.
    Use this for passive crafting when you only need to generate packet structure.
    
    Args:
        pkt_desc: A JSON string describing protocol layers and their fields.
    
    Returns:
        JSON representation of the crafted packet.
    """
    try:
        layers = json.loads(pkt_desc)
        return json.dumps(layers, indent=2)
    except json.JSONDecodeError as e:
        return f"Invalid JSON: {e}"


@tool
def ping_host(target: str, count: int = 4, timeout: int = 2, arguments: Optional[str] = None) -> str:
    """
    Ping a host to check if it's reachable.
    
    Args:
        target: IP address or hostname to ping.
        count: Number of ping requests to send (default: 4).
        timeout: Timeout in seconds for each ping (default: 2).
        arguments: Additional arguments for ping command.
    """
    # Delegate to the standalone ping function
    result = ping(target, count, timeout, arguments)
    
    if result["success"]:
        return result["raw_output"].strip()
    return f"Ping failed: {result['raw_output']}"


@tool
def traceroute_host(target: str, max_hops: int = 30, use_scapy: bool = True, arguments: Optional[str] = None) -> str:
    """
    Perform a traceroute to discover the path to a target host.
    
    Args:
        target: IP address or hostname to trace.
        max_hops: Maximum number of hops to trace (default: 30).
        use_scapy: Use Scapy's traceroute (True) or system traceroute (False).
        arguments: Additional arguments for system traceroute.
    """
    max_hops = min(max(1, max_hops), 64)
    
    if not re.match(r'^[\w\.\-]+$', target):
        return "Invalid target format"
    
    if use_scapy:
        try:
            result, _ = scapy_traceroute(target, maxttl=max_hops, verbose=0)
            if result:
                output = ["Scapy Traceroute Results:"]
                for snd, rcv in result:
                    output.append(f"  {snd.ttl}: {rcv.src}")
                return "\n".join(output)
            return "No response from any hop"
        except Exception as e:
            return f"Scapy traceroute error: {e}"
    else:
        # Delegate to the standalone traceroute function
        result = traceroute(target, max_hops, timeout=3, arguments=arguments)
        if result["success"]:
            return result["raw_output"]
        return f"Traceroute failed: {result['raw_output']}"


@tool
def nmap_scan(
    target: str,
    scan_type: str = "basic",
    ports: Optional[str] = None,
    arguments: Optional[str] = None
) -> str:
    """
    Perform an NMAP scan on a target.
    
    Args:
        target: IP address, hostname, or CIDR range to scan.
        scan_type: Type of scan - "basic", "quick", "intense", "ping", "version", "os".
        ports: Specific ports to scan (e.g., "22,80,443" or "1-1000").
        arguments: Additional NMAP arguments (advanced users only).
    
    Returns:
        NMAP scan results.
    """
    # Delegate to the standalone nmap_scan_direct function
    result = nmap_scan_direct(target, scan_type, ports, arguments)
    
    if result["success"]:
        return result["raw_output"]
    return f"NMAP failed: {result['raw_output']}"


@tool
def hping3_probe(
    target: str,
    mode: str = "syn",
    port: int = 80,
    count: int = 4,
    flags: Optional[str] = None,
    arguments: Optional[str] = None
) -> str:
    """
    Use hping3 for advanced packet probing and testing.
    
    Args:
        target: IP address or hostname to probe.
        mode: Probe mode - "syn", "ack", "fin", "udp", "icmp", "rawip".
        port: Target port (default: 80).
        count: Number of packets to send (default: 4).
        flags: Custom TCP flags (e.g., "SAF" for SYN+ACK+FIN).
        arguments: Additional hping3 arguments.
    """
    if not shutil.which("hping3"):
        return "hping3 is not installed. Please install with: sudo apt install hping3"
    
    if not re.match(r'^[\w\.\-]+$', target):
        return "Invalid target format"
    
    port = min(max(1, port), 65535)
    count = min(max(1, count), 100)
    
    mode_flags = {
        "syn": "-S",
        "ack": "-A",
        "fin": "-F",
        "udp": "-2",
        "icmp": "-1",
        "rawip": "-0",
    }
    
    cmd = ["hping3", "-c", str(count)]
    
    if flags and mode == "syn":
        for f in flags.upper():
            flag_map = {"S": "-S", "A": "-A", "F": "-F", "R": "-R", "U": "-U", "P": "-P"}
            if f in flag_map:
                cmd.append(flag_map[f])
    else:
        cmd.append(mode_flags.get(mode, "-S"))
    
    if mode not in ["icmp", "rawip"]:
        cmd.extend(["-p", str(port)])
    
    if arguments:
        cmd.extend(arguments.split())

    cmd.append(target)
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=count * 5 + 10
        )
        output = result.stdout + result.stderr
        return output if output.strip() else "No output from hping3"
    except subprocess.TimeoutExpired:
        return "hping3 timed out"
    except Exception as e:
        return f"hping3 error: {e}"


@tool
def quick_port_scan(target: str, ports: str = "22,80,443,8080,8443") -> str:
    """
    Perform a quick TCP port scan using Scapy.
    
    Args:
        target: IP address to scan.
        ports: Comma-separated list of ports to scan.
    
    Returns:
        Scan results showing open/closed ports.
    """
    if not re.match(r'^[\d\.]+$', target):
        return "Invalid IP address format"
    
    try:
        port_list = [int(p.strip()) for p in ports.split(",")]
        port_list = [p for p in port_list if 1 <= p <= 65535][:50]
    except ValueError:
        return "Invalid ports format. Use comma-separated integers."
    
    results = []
    for port in port_list:
        try:
            pkt = IP(dst=target) / TCP(dport=port, flags="S")
            answered, _ = sr(pkt, timeout=1, verbose=0)
            
            if answered:
                response = answered[0][1]
                if response.haslayer(TCP):
                    flags = response[TCP].flags
                    if flags == 0x12:
                        results.append(f"Port {port}: OPEN")
                        rst = IP(dst=target) / TCP(dport=port, flags="R")
                        send(rst, verbose=0)
                    elif flags == 0x14:
                        results.append(f"Port {port}: CLOSED")
            else:
                results.append(f"Port {port}: FILTERED (no response)")
        except Exception as e:
            results.append(f"Port {port}: ERROR ({e})")
    
    return "Quick Port Scan Results:\n" + "\n".join(results)


@tool
def arp_scan(network: str = "192.168.1.0/24") -> str:
    """
    Perform an ARP scan to discover hosts on the local network.
    
    Args:
        network: Network range in CIDR notation (e.g., "192.168.1.0/24").
    
    Returns:
        List of discovered hosts with their IP and MAC addresses.
    """
    if not re.match(r'^[\d\.]+/\d+$', network):
        return "Invalid network format. Use CIDR notation like '192.168.1.0/24'"
    
    try:
        pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=network)
        answered, _ = srp(pkt, timeout=2, verbose=0)
        
        if not answered:
            return "No hosts discovered"
        
        results = ["ARP Scan Results:", "-" * 40]
        for sent, received in answered:
            results.append(f"IP: {received.psrc:15} MAC: {received.hwsrc}")
        
        results.append("-" * 40)
        results.append(f"Total hosts found: {len(answered)}")
        return "\n".join(results)
    except Exception as e:
        return f"ARP scan error: {e}"


@tool
def dns_lookup_tool(
    target: str,
    record_types: str = "A",
    nameserver: Optional[str] = None
) -> str:
    """
    Perform DNS lookups for various record types.
    
    Args:
        target: Domain name to query.
        record_types: Comma-separated list of record types (A, AAAA, MX, NS, TXT, SOA, CNAME, PTR, SRV, CAA).
        nameserver: Optional DNS server to use (e.g., "8.8.8.8").
    
    Returns:
        DNS query results for all requested record types.
    """
    try:
        import dns.resolver
        import dns.reversename
    except ImportError:
        return "dnspython is not installed. Please install with: pip install dnspython"
    
    valid_types = {"A", "AAAA", "MX", "NS", "TXT", "SOA", "CNAME", "PTR", "SRV", "CAA", "ANY"}
    requested_types = [t.strip().upper() for t in record_types.split(",")]
    requested_types = [t for t in requested_types if t in valid_types]
    
    if not requested_types:
        requested_types = ["A"]
    
    resolver = dns.resolver.Resolver()
    if nameserver:
        resolver.nameservers = [nameserver]
    
    results = [f"DNS Lookup Results for: {target}", "=" * 50]
    
    for record_type in requested_types:
        results.append(f"\n[{record_type} Records]")
        try:
            if record_type == "PTR":
                try:
                    rev_name = dns.reversename.from_address(target)
                    answers = resolver.resolve(rev_name, "PTR")
                except:
                    answers = resolver.resolve(target, "PTR")
            else:
                answers = resolver.resolve(target, record_type)
            
            for rdata in answers:
                if record_type == "MX":
                    results.append(f"  Priority: {rdata.preference}, Mail Server: {rdata.exchange}")
                elif record_type == "SOA":
                    results.append(f"  Primary NS: {rdata.mname}")
                    results.append(f"  Admin: {rdata.rname}")
                    results.append(f"  Serial: {rdata.serial}")
                    results.append(f"  Refresh: {rdata.refresh}s, Retry: {rdata.retry}s")
                    results.append(f"  Expire: {rdata.expire}s, Minimum TTL: {rdata.minimum}s")
                elif record_type == "SRV":
                    results.append(f"  Priority: {rdata.priority}, Weight: {rdata.weight}")
                    results.append(f"  Port: {rdata.port}, Target: {rdata.target}")
                else:
                    results.append(f"  {rdata}")
        except dns.resolver.NXDOMAIN:
            results.append(f"  Domain does not exist")
        except dns.resolver.NoAnswer:
            results.append(f"  No {record_type} records found")
        except dns.resolver.NoNameservers:
            results.append(f"  No nameservers available")
        except Exception as e:
            results.append(f"  Error: {e}")
    
    return "\n".join(results)


@tool
def final_report(report: str) -> str:
    """
    Submit the final analysis report.
    Use this tool when you have completed your analysis and want to provide results.
    
    Args:
        report: The final report text to submit.
    
    Returns:
        The report content (signals completion).
    """
    return report


def ping(target: str, count: int = 4, timeout: int = 5, arguments: Optional[str] = None) -> dict:
    # Add input validation clamps
    count = min(max(1, count), 20)
    timeout = min(max(1, timeout), 10)
    
    if not re.match(r'^[\w\.\-]+$', target):
        return {"success": False, "target": target, "raw_output": "Invalid target format",
                "packets_sent": 0, "packets_received": 0, "packet_loss": 100.0}
    
    try:
        cmd = ["ping", "-c", str(count), "-W", str(timeout)]
        if arguments:
            cmd.extend(arguments.split())
        cmd.append(target)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=count * timeout + 5
        )
        
        output = result.stdout
        success = result.returncode == 0
        
        packets_sent = count
        packets_received = 0
        packet_loss = 100.0
        rtt_min = rtt_avg = rtt_max = None
        
        loss_match = re.search(r'(\d+)% packet loss', output)
        if loss_match:
            packet_loss = float(loss_match.group(1))
            packets_received = int(count * (100 - packet_loss) / 100)
        
        rtt_match = re.search(r'rtt min/avg/max/mdev = ([\d.]+)/([\d.]+)/([\d.]+)', output)
        if rtt_match:
            rtt_min = float(rtt_match.group(1))
            rtt_avg = float(rtt_match.group(2))
            rtt_max = float(rtt_match.group(3))
        
        return {
            "success": success,
            "target": target,
            "packets_sent": packets_sent,
            "packets_received": packets_received,
            "packet_loss": packet_loss,
            "rtt_min": rtt_min,
            "rtt_avg": rtt_avg,
            "rtt_max": rtt_max,
            "raw_output": output
        }
    except Exception as e:
        return {"success": False, "target": target, "raw_output": str(e),
                "packets_sent": count, "packets_received": 0, "packet_loss": 100.0}


def nmap_scan_direct(target: str, scan_type: str = "quick", ports: Optional[str] = None, arguments: Optional[str] = None) -> dict:
    if not shutil.which("nmap"):
        return {"success": False, "target": target, "scan_type": scan_type,
                "open_ports": [], "raw_output": "NMAP not installed"}

    if not re.match(r'^[\w\.\-\/]+$', target):
        return {"success": False, "target": target, "scan_type": scan_type,
                "open_ports": [], "raw_output": "Invalid target format"}
    
    scan_args = {
        "basic": ["-sT", "-T3"],
        "quick": ["-sn"],
        "intense": ["-sS", "-sV", "-T4"],
        "ping": ["-sn", "-PE"],
        "version": ["-sV"],
        "os": ["-O"],
    }
    
    cmd = ["nmap"]
    cmd.extend(scan_args.get(scan_type, scan_args["basic"]))
    
    if ports and re.match(r'^[\d,\-]+$', ports):
        cmd.extend(["-p", ports])

    if arguments:
        cmd.extend(arguments.split())
    
    cmd.append(target)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        open_ports = []
        for line in result.stdout.split('\n'):
            port_match = re.match(r'^(\d+)/(\w+)\s+open\s+(\S+)', line)
            if port_match:
                open_ports.append({
                    "port": int(port_match.group(1)),
                    "protocol": port_match.group(2),
                    "service": port_match.group(3)
                })
        
        return {
            "success": result.returncode == 0,
            "target": target,
            "scan_type": scan_type,
            "open_ports": open_ports,
            "raw_output": result.stdout
        }
    except Exception as e:
        return {"success": False, "target": target, "scan_type": scan_type,
                "open_ports": [], "raw_output": str(e)}


def traceroute(target: str, max_hops: int = 30, timeout: int = 5, arguments: Optional[str] = None) -> dict:
    max_hops = min(max(1, max_hops), 64)
    
    if not re.match(r'^[\w\.\-]+$', target):
        return {"success": False, "target": target, "hops": [], "raw_output": "Invalid target"}
    
    try:
        cmd = ["traceroute", "-m", str(max_hops), "-w", str(timeout)]
        if arguments:
            cmd.extend(arguments.split())
        cmd.append(target)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max_hops * timeout
        )
        
        hops = []
        for line in result.stdout.split('\n'):
            # Match: hop hostname (ip) ...
            hop_match = re.match(r'\s*(\d+)\s+(\S+)\s+\(([\d.]+)\)(.*)', line)
            if hop_match:
                hop_num = int(hop_match.group(1))
                hostname = hop_match.group(2)
                ip = hop_match.group(3)
                remainder = hop_match.group(4)
                
                # Extract RTTs (looking for "X ms" or just numbers)
                # Typical output:  1.234 ms  2.345 ms
                rtts = re.findall(r'([\d\.]+)\s+ms', remainder)
                
                # Calculate average RTT if any valid RTTs found
                if rtts:
                    try:
                        avg_rtt = sum(float(r) for r in rtts) / len(rtts)
                        rtt_str = f"{avg_rtt:.2f} ms"
                    except ValueError:
                        rtt_str = rtts[0] + " ms"
                else:
                    rtt_str = "*"
                    
                hops.append({
                    "hop": hop_num,
                    "hostname": hostname,
                    "ip": ip,
                    "rtt": rtt_str
                })
        
        return {
            "success": result.returncode == 0,
            "target": target,
            "hops": hops,
            "raw_output": result.stdout
        }
    except Exception as e:
        return {"success": False, "target": target, "hops": [], "raw_output": str(e)}


def dns_lookup(target: str, record_type: str = "A") -> dict:
    try:
        import dns.resolver
        
        resolver = dns.resolver.Resolver()
        answers = resolver.resolve(target, record_type)
        records = [str(rdata) for rdata in answers]
        
        return {
            "success": True,
            "target": target,
            "record_type": record_type,
            "records": records,
            "raw_output": "\n".join(records)
        }
    except Exception as e:
        return {
            "success": False,
            "target": target,
            "record_type": record_type,
            "records": [],
            "raw_output": str(e)
        }


def check_nmap_available() -> bool:
    return shutil.which("nmap") is not None


ALL_TOOLS = [
    send_packet,
    craft_packet_json,
    ping_host,
    traceroute_host,
    nmap_scan,
    hping3_probe,
    quick_port_scan,
    arp_scan,
    dns_lookup_tool,
]

ALL_TOOLS_WITH_REPORT = ALL_TOOLS + [final_report]

TOOL_MAP = {tool.name: tool.func for tool in ALL_TOOLS}
TOOL_MAP["final_report"] = final_report.func
