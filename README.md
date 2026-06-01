# AI Proxy Router

Round-robin proxy router untuk 3 AI provider dengan automatic failover.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env, isi API key
```

## Jalankan

```bash
python main.py
```

## Endpoint

| Method | Endpoint | Format |
|--------|----------|--------|
| POST | `/v1/messages` | Anthropic (Claude Code) |
| POST | `/v1/chat/completions` | OpenAI |
| GET | `/health` | Health check |

## .env

```env
PORT=8080
REQUEST_TIMEOUT=30
MAX_RETRIES=1

GLM_API_KEY=
DATABYTE_API_KEY=
KONEKTIKA_API_KEY=
```

Kosongkan API key untuk skip model. Semua kosong = warning + proxy tidak aktif.

## Claude Code

```bash
claude --anthropic-base-url http://localhost:8080/v1/messages
```