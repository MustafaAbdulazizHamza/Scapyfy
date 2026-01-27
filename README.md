# Scapyfy v2.0.0

![Alt text](https://github.com/MustafaAbdulazizHamza/Scapyfy/blob/main/scapyfy.png)
---
**Scapyfy** is an AI-powered network security toolkit that combines LLM intelligence with powerful packet crafting capabilities. It provides both an **LLM agent** for automated network analysis and **direct tool access** for manual operations. The platform supports **multiple LLM providers** (OpenAI, Google Gemini, Anthropic Claude, Ollama), features a modern **web interface**, and exposes a **REST API** secured with **JWT authentication** and **TLS** support.

---

## Features

### Multi-LLM Support
- **OpenAI** (GPT-3.5, GPT-4)
- **Google Gemini** (Gemini 1.5 Flash/Pro)
- **Anthropic Claude** (Claude 3.5 Sonnet)
- **Ollama** (Local)

### Network Tools
- **Packet Crafting** (Scapy) - Custom TCP/IP/UDP/ICMP packets
- **Nmap Scanner** - Port scanning, service detection, OS fingerprinting
- **Traceroute** - Network path discovery
- **Ping** - Host reachability testing
- **Hping3** - Advanced packet probing
- **Port Scanner** - Fast Scapy-based scanning
- **ARP Scanner** - Local network discovery

## Requirements

To run Scapyfy, you will need the following:

1. A **Linux machine** (desktop, server, etc.)
2. **Superuser privileges** (`sudo`) for packet crafting
3. **Python 3.10+**
4. At least one **LLM API Key** (OpenAI, Google, or Anthropic) OR a running **Ollama** instance

### System Dependencies
```bash
# For Nmap scanning
sudo apt install nmap

# For Hping3 
sudo apt install hping3

# For traceroute
sudo apt install traceroute
```


## Installation

Follow these steps to get Scapyfy set up:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/MustafaAbdulazizHamza/Scapyfy.git
   cd Scapyfy
   ```

2. **Create and activate virtual environment:**
   ```bash
   python3 -m venv env
   source env/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Create a `.env` file based on the configuration specified in `env.example` file. 


## Execution

Since packet crafting requires low-level access, run with **superuser privileges**:

### Without TLS
```bash
sudo bash execute.sh
```

### With TLS
```bash
# Using your own certificates
sudo bash execute.sh --ssl-cert /path/to/server.crt --ssl-key /path/to/server.key
```

## Notes

1. **API Documentation**: Available at `/docs` (Swagger UI) and `/redoc` (ReDoc) after starting the server
2. **Logs**: Execution logs are stored in `./logs/scapyfy_executions.log`
3. **Security**: Always change the generated root password, set a strong `SECRET_KEY`, and run the server on a dedicated virtual machine in production.



## Disclaimer

- This project is designed for **educational purposes** and authorized security testing only.

- **Always ensure you have proper authorization before performing network scans or packet injection.**
