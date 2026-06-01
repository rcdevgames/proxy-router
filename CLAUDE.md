# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

AI Proxy Router - round-robin load balancer dan failover untuk 3 AI provider (GLM, DataByte, Konektika). Mendukung format API Anthropic dan OpenAI.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev
python main.py

# Service management (Linux)
sudo bash service.sh install   # Install systemd service
sudo bash service.sh start      # Start service
sudo bash service.sh stop       # Stop service
sudo bash service.sh restart    # Restart
sudo bash service.sh status     # Check status

# Use with Claude Code
claude --anthropic-base-url http://localhost:8080/v1/messages
```

## Architecture

```
main.py          # FastAPI app, startup initialization
router.py        # ProxyRouter class - round-robin logic, failover, format transformation
config.py        # Settings via pydantic_settings, model config loader
```

**ProxyRouter** (`router.py`) handles:
- Priority-based model selection: Konektika → DataByte → GLM
- Request/response format transformation (Anthropic ↔ OpenAI)
- Automatic failover: tries next model on timeout/HTTP error
- Streaming support untuk kedua format

**Model Format Support:**
| Provider | API Format | Transform |
|----------|------------|-----------|
| Konektika | OpenAI | Transform request/response |
| DataByte | Anthropic native | None |
| GLM | Anthropic native | None |

## Authentication

Semua endpoint kecuali `/health` butuh `X-Api-Key` header. Set `PROXY_API_KEY` di `.env`.

Model validation: client submit model name, proxy validasi against `ALLOWED_MODELS` (formalitas, proxy route pakai priority order bukan model dari client).

## Environment Variables

```
PORT=8080
REQUEST_TIMEOUT=30
MAX_RETRIES=1
PROXY_API_KEY=           # Required untuk akses API
ALLOWED_MODELS=databyte-m1,kimi-pro,GLM-4.7  # Validation only

# Model Priority (1-3): Konektika -> DataByte -> GLM
KONEKTIKA_API_KEY=
DATABYTE_API_KEY=
GLM_API_KEY=
```

## Key Behavior

- Startup: exit code 1 kalau ga ada model aktif
- Routing: always try highest priority first, fallback on failure
- Auth: 401 kalau `X-Api-Key` invalid/missing (kecuali `/health`)
- Model validation: 403 kalau model tidak ada di `ALLOWED_MODELS`