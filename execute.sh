#!/bin/bash
# Scapyfy Execution Script
# Usage: sudo bash execute.sh [options]
#
# Options:
#   --ssl-cert <path>     Path to SSL certificate file
#   --ssl-key <path>      Path to SSL key file
#   --ssl-ca <path>       Path to CA certificates (for client verification)
#   --ssl-verify <level>  Client cert verification: none, optional, required
#   --no-reload           Disable auto-reload (for production)
#   --help                Show this help message

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_banner() {
    echo -e "${CYAN}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║           🧙‍♂️ Scapyfy - AI Packet Crafter                 ║"
    echo "║                    Version 2.0.0                         ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_help() {
    echo "Usage: sudo bash execute.sh [options]"
    echo ""
    echo "Options:"
    echo "  --ssl-cert <path>         Path to SSL certificate file"
    echo "  --ssl-key <path>          Path to SSL key file"
    echo "  --ssl-ca <path>           Path to CA certificates (for mTLS)"
    echo "  --ssl-verify <level>      Client cert verification: none, optional, required"
    echo "  --no-reload               Disable auto-reload (for production)"
    echo "  --help                    Show this help message"
    echo ""
    echo "Examples:"
    echo "  sudo bash execute.sh"
    echo "  sudo bash execute.sh --ssl-cert server.crt --ssl-key server.key"
    echo "  sudo bash execute.sh --ssl-cert server.crt --ssl-key server.key --ssl-ca ca.crt --ssl-verify required"
    echo ""
    echo "Quick Certificate Generation:"
    echo "  openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt -days 365 -nodes"
}

print_banner

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ Please run with sudo: sudo bash execute.sh${NC}"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SSL_CERTFILE=""
SSL_KEYFILE=""
SSL_CA_CERTS=""
SSL_CERT_REQS="0"
NO_RELOAD=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --ssl-cert)
            SSL_CERTFILE="$2"
            shift 2
            ;;
        --ssl-key)
            SSL_KEYFILE="$2"
            shift 2
            ;;
        --ssl-ca)
            SSL_CA_CERTS="$2"
            shift 2
            ;;
        --ssl-verify)
            case $2 in
                none) SSL_CERT_REQS="0" ;;
                optional) SSL_CERT_REQS="1" ;;
                required) SSL_CERT_REQS="2" ;;
                *) echo -e "${RED}Invalid --ssl-verify value: $2${NC}"; exit 1 ;;
            esac
            shift 2
            ;;
        --no-reload)
            NO_RELOAD=true
            shift
            ;;
        --help|-h)
            print_help
            exit 0
            ;;
        *)
            echo -e "${YELLOW}Unknown option: $1${NC}"
            print_help
            exit 1
            ;;
    esac
done

for VENV in "env" "venv" "scapyfy-env" ".venv"; do
    if [ -d "$VENV" ]; then
        echo -e "${GREEN}✅ Activating virtual environment: ${VENV}${NC}"
        source "$VENV/bin/activate"
        break
    fi
done

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo -e "${BLUE}🐍 Python ${PYTHON_VERSION}${NC}"

if [ -f ".env" ]; then
    echo -e "${GREEN}✅ Loaded .env${NC}"
    set -a
    source .env
    set +a
fi

echo -e "${BLUE}🤖 LLM Providers:${NC}"
PROVIDERS_FOUND=0

if [ -n "$OPENAI_API_KEY" ]; then
    echo -e "   ${GREEN}✓ OpenAI${NC}"
    PROVIDERS_FOUND=$((PROVIDERS_FOUND + 1))
fi

if [ -n "$GOOGLE_API_KEY" ] || [ -n "$GEMINI_API_KEY" ]; then
    echo -e "   ${GREEN}✓ Gemini${NC}"
    PROVIDERS_FOUND=$((PROVIDERS_FOUND + 1))
fi

if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo -e "   ${GREEN}✓ Claude${NC}"
    PROVIDERS_FOUND=$((PROVIDERS_FOUND + 1))
fi

OLLAMA_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
if curl -s --max-time 2 "$OLLAMA_URL/api/tags" > /dev/null 2>&1; then
    echo -e "   ${GREEN}✓ Ollama (${OLLAMA_URL})${NC}"
    PROVIDERS_FOUND=$((PROVIDERS_FOUND + 1))
fi

if [ $PROVIDERS_FOUND -eq 0 ]; then
    echo -e "${RED}❌ No LLM providers configured!${NC}"
    echo "   Set OPENAI_API_KEY, GOOGLE_API_KEY, ANTHROPIC_API_KEY, or run Ollama"
    exit 1
fi

echo -e "${BLUE}🔧 Network Tools:${NC}"
for tool in nmap hping3 traceroute; do
    if command -v $tool &> /dev/null; then
        echo -e "   ${GREEN}✓ ${tool}${NC}"
    else
        echo -e "   ${YELLOW}⚠ ${tool} not found${NC}"
    fi
done

LOGS_DIR="${LOGS_DIR:-logs}"
mkdir -p "$LOGS_DIR"
LOG_ROTATION="${LOG_ROTATION_HOURS:-24}"
echo -e "${BLUE}📝 Logging:${NC}"
echo -e "   ${GREEN}✓ Directory: ${LOGS_DIR}${NC}"
echo -e "   ${GREEN}✓ Rotation: every ${LOG_ROTATION}h${NC}"

[ -z "$SECRET_KEY" ] && echo -e "${YELLOW}⚠️  SECRET_KEY not set (auto-generated)${NC}"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
UVICORN_ARGS="--host $HOST --port $PORT"

if [ -n "$SSL_CERTFILE" ] && [ -n "$SSL_KEYFILE" ]; then
    [ ! -f "$SSL_CERTFILE" ] && echo -e "${RED}❌ Certificate not found: $SSL_CERTFILE${NC}" && exit 1
    [ ! -f "$SSL_KEYFILE" ] && echo -e "${RED}❌ Key not found: $SSL_KEYFILE${NC}" && exit 1
    
    UVICORN_ARGS="$UVICORN_ARGS --ssl-certfile $SSL_CERTFILE --ssl-keyfile $SSL_KEYFILE"
    
    if [ -n "$SSL_CA_CERTS" ]; then
        [ ! -f "$SSL_CA_CERTS" ] && echo -e "${RED}❌ CA cert not found: $SSL_CA_CERTS${NC}" && exit 1
        UVICORN_ARGS="$UVICORN_ARGS --ssl-ca-certs $SSL_CA_CERTS --ssl-cert-reqs $SSL_CERT_REQS"
        VERIFY_LEVEL="NONE"; [ "$SSL_CERT_REQS" = "1" ] && VERIFY_LEVEL="OPTIONAL"; [ "$SSL_CERT_REQS" = "2" ] && VERIFY_LEVEL="REQUIRED"
        echo -e "${BLUE}🔐 Client verification: ${VERIFY_LEVEL}${NC}"
    fi
    
    echo ""
    echo -e "${GREEN}🔒 Starting with TLS${NC}"
    echo -e "${CYAN}📡 https://${HOST}:${PORT}${NC}"
    echo -e "${CYAN}📚 https://${HOST}:${PORT}/docs${NC}"
    echo ""
    
    [ "$NO_RELOAD" = false ] && UVICORN_ARGS="$UVICORN_ARGS --reload"
    python3 -m uvicorn main:app $UVICORN_ARGS
else
    echo ""
    echo -e "${YELLOW}🔓 Starting without TLS (dev mode)${NC}"
    echo -e "${CYAN}📡 http://${HOST}:${PORT}${NC}"
    echo -e "${CYAN}📚 http://${HOST}:${PORT}/docs${NC}"
    echo ""
    
    [ "$NO_RELOAD" = false ] && UVICORN_ARGS="$UVICORN_ARGS --reload"
    python3 -m uvicorn main:app $UVICORN_ARGS
fi