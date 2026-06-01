import uvicorn
from fastapi import FastAPI, Request, Response, Header, HTTPException, Depends
from fastapi.responses import StreamingResponse
from config import load_settings
from router import ProxyRouter


app = FastAPI(title="AI Proxy Router")
router = None
proxy_api_key = None


def get_api_key(x_api_key: str = Header(None)) -> str:
    """Verify API key - required untuk semua route kecuali /health"""
    if not proxy_api_key:
        return x_api_key  # Auth disabled if key not set
    if x_api_key != proxy_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


@app.on_event("startup")
async def startup():
    global router, proxy_api_key
    settings = load_settings()

    # Load proxy API key
    proxy_api_key = settings.proxy_api_key or None

    # Kalau tidak ada model aktif, stop service dengan exit code 1
    models = settings.get_models()
    if not models:
        print("\n[CRITICAL] Tidak ada model yang aktif!")
        print("Set setidaknya satu API key di .env untuk menjalankan proxy.\n")
        import os
        os._exit(1)

    router = ProxyRouter(settings)
    print(f"\n[OK] Proxy router aktif dengan {len(router.models)} model:")
    for m in router.models:
        print(f"   - {m.model} ({m.base_url})")
    if proxy_api_key:
        print(f"   [Auth] API key protection enabled")


@app.post("/v1/messages")
async def anthropic_messages(request: Request, _: str = Depends(get_api_key)):
    """Anthropic native format endpoint (Claude Code style)"""
    if router is None:
        return Response(content="Proxy tidak aktif - tidak ada model tersedia", status_code=503)

    try:
        data = await request.json()
        is_anthropic_format = True

        if data.get("stream"):
            async def stream_response():
                try:
                    async for chunk in router.handle_request(data, is_anthropic_format):
                        yield f"data: {chunk}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    yield f'data: {{"error": "{str(e)}"}}\n\n'

            return StreamingResponse(
                stream_response(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        else:
            result = await router.handle_request(data, is_anthropic_format)
            return result

    except Exception as e:
        return Response(content=str(e), status_code=500)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request, _: str = Depends(get_api_key)):
    """OpenAI-compatible endpoint"""
    if router is None:
        return Response(content="Proxy tidak aktif - tidak ada model tersedia", status_code=503)

    try:
        data = await request.json()
        is_anthropic_format = False

        if data.get("stream"):
            async def stream_response():
                try:
                    async for chunk in router.handle_request(data, is_anthropic_format):
                        yield f"data: {chunk}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    yield f'data: {{"error": "{str(e)}"}}\n\n'

            return StreamingResponse(
                stream_response(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                }
            )
        else:
            result = await router.handle_request(data, is_anthropic_format)
            return result

    except Exception as e:
        return Response(content=str(e), status_code=500)


@app.get("/health")
async def health():
    """Health check endpoint - NO auth required"""
    return {
        "status": "ok" if router else "degraded",
        "models": [m.model for m in router.models] if router else []
    }


@app.get("/")
async def root():
    return {
        "name": "AI Proxy Router",
        "endpoints": ["/v1/messages", "/v1/chat/completions"],
        "health": "/health"
    }


if __name__ == "__main__":
    settings = load_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=False
    )