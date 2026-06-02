import uvicorn
from fastapi import FastAPI, Request, Response, Header, HTTPException, Depends
from fastapi.responses import StreamingResponse
from config import load_settings
from router import ProxyRouter


app = FastAPI(title="AI Proxy Router")
router = None
proxy_api_key = None
allowed_model_name = None


def get_api_key(
    x_api_key: str = Header(None),
    authorization: str = Header(None)
) -> str:
    """Verify API key - accept X-Api-Key or Authorization: Bearer header"""
    if not proxy_api_key:
        return x_api_key or authorization
    
    if x_api_key and x_api_key == proxy_api_key:
        return x_api_key
    
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
        if token == proxy_api_key:
            return token
    
    raise HTTPException(status_code=401, detail="Invalid API key")


@app.on_event("startup")
async def startup():
    global router, proxy_api_key, allowed_model_name
    settings = load_settings()

    # Load proxy API key
    proxy_api_key = settings.proxy_api_key or None

    # Load exposed model name
    allowed_model_name = settings.model_name

    # Build priority list untuk cek model yang tersedia
    from router import ProxyRouter
    priority_models = []
    if settings.konektika_api_key and settings.konektika_enabled:
        priority_models.append("Konektika")
    if settings.databyte_api_key and settings.databyte_enabled:
        priority_models.append("DataByte")
    if settings.glm_api_key and settings.glm_enabled:
        priority_models.append("GLM")

    # Kalau tidak ada model aktif, stop service dengan exit code 1
    if not priority_models:
        print("\n[CRITICAL] Tidak ada model yang aktif!")
        print("Set setidaknya satu API key di .env untuk menjalankan proxy.\n")
        import os
        os._exit(1)

    router = ProxyRouter(settings)
    print(f"\n[OK] Proxy router aktif:")
    print(f"   Model name: {allowed_model_name}")
    print(f"   Priority: {', '.join(m.model for m in router.models)}")
    if proxy_api_key:
        print(f"   [Auth] API key protection enabled")


@app.post("/v1/messages")
async def anthropic_messages(request: Request, _: str = Depends(get_api_key)):
    """Anthropic native format endpoint (Claude Code style)"""
    if router is None:
        return Response(content="Proxy tidak aktif - tidak ada model tersedia", status_code=503)

    try:
        data = await request.json()

        # Validasi model name - HARUS exact match dengan exposed model name
        requested_model = data.get("model", "")
        if requested_model and requested_model != allowed_model_name:
            return Response(
                content=f"Bad Request: model '{requested_model}' tidak tersedia. Gunakan model name yang正确.",
                status_code=400
            )

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