#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PARENT_DIR="$(dirname "$SCRIPT_DIR")"

source "${SCRIPT_DIR}/scapyfy-env/bin/activate"

UVICORN_CMD="${SCRIPT_DIR}/scapyfy-env/bin/uvicorn main:app --host 0.0.0.0 --port 8000"

if [ -n "$1" ] && [ -n "$2" ]; then
    UVICORN_CMD="${UVICORN_CMD} --ssl-certfile=$1 --ssl-keyfile=$2"
fi

sudo HOME="${HOME}" PYTHONPATH="${PARENT_DIR}:${PYTHONPATH}" bash -c "${UVICORN_CMD}"
