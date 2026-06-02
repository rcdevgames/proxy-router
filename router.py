import httpx
import json
from typing import AsyncGenerator, Optional
from config import Settings, ModelConfig


class ProxyRouter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.exposed_model_name = settings.model_name
        # Priority order: Konektika (1) -> DataByte (2) -> GLM (3)
        self.models = self._build_priority_list(settings)
        self.current_index = 0

        if not self.models:
            raise ValueError("Tidak ada model yang tersedia. Set API key di .env")

    def _build_priority_list(self, settings: Settings) -> list[ModelConfig]:
        """Build priority-based model list: Konektika -> DataByte -> GLM"""
        models = []

        # Priority 1: Konektika
        if settings.konektika_api_key and settings.konektika_enabled:
            models.append(ModelConfig(
                api_key=settings.konektika_api_key,
                base_url=settings.konektika_base_url,
                model=settings.konektika_model,
                enabled=True,
                supports_anthropic_format=False  # OpenAI format
            ))

        # Priority 2: DataByte
        if settings.databyte_api_key and settings.databyte_enabled:
            models.append(ModelConfig(
                api_key=settings.databyte_api_key,
                base_url=settings.databyte_base_url,
                model=settings.databyte_model,
                enabled=True,
                supports_anthropic_format=True
            ))

        # Priority 3: GLM (fallback last resort)
        if settings.glm_api_key and settings.glm_enabled:
            models.append(ModelConfig(
                api_key=settings.glm_api_key,
                base_url=settings.glm_base_url,
                model=settings.glm_model,
                enabled=True,
                supports_anthropic_format=True
            ))

        return models

    def _get_next_model(self) -> ModelConfig:
        """Priority-based: always try from start, failover to next"""
        if not self.models:
            raise ValueError("Tidak ada model yang tersedia")

        # Reset to first (priority highest) on each request for retry
        if self.current_index >= len(self.models):
            self.current_index = 0

        model = self.models[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.models)
        return model

    def _transform_to_openai(self, data: dict) -> dict:
        """Transform request Anthropic format ke OpenAI format"""
        messages = data.get("messages", [])
        anthropic_system = data.get("system", "")

        # Combine system into first message if exists
        if anthropic_system:
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = f"{anthropic_system}\n\n{messages[0]['content']}"
            else:
                messages.insert(0, {
                    "role": "system",
                    "content": anthropic_system
                })

        return {
            "model": "",  # Will be set per model
            "messages": messages,
            "stream": data.get("stream", False),
            "max_tokens": data.get("max_tokens", 4096),
        }

    def _transform_from_openai(self, response_data: dict, target_format: str) -> dict:
        """Transform response dari OpenAI ke Anthropic format"""
        if target_format == "anthropic":
            # Convert OpenAI response ke Anthropic format
            content = response_data.get("choices", [{}])[0].get("message", {}).get("content", "")

            return {
                "type": "message",
                "role": "assistant",
                "content": content,
                "id": response_data.get("id", "msg_xxx"),
                "model": self.exposed_model_name,  # Use exposed name
                "stop_reason": response_data.get("choices", [{}])[0].get("finish_reason", "end_turn"),
                "stop_sequence": None,
                "usage": {
                    "input_tokens": response_data.get("usage", {}).get("prompt_tokens", 0),
                    "output_tokens": response_data.get("usage", {}).get("completion_tokens", 0),
                }
            }
        return response_data

    async def _call_model(
        self,
        model: ModelConfig,
        data: dict,
        is_anthropic_format: bool
    ) -> dict:
        """Panggil satu model dengan retry"""
        headers = {
            "Authorization": f"Bearer {model.api_key}",
            "Content-Type": "application/json"
        }

        timeout = httpx.Timeout(self.settings.request_timeout, connect=10.0)

        # Tentukan provider name untuk logging
        provider_name = "Konektika" if "konektika" in model.base_url.lower() else \
                        "DataByte" if "databyte" in model.base_url.lower() else \
                        "GLM" if "glm" in model.base_url.lower() else model.base_url
        
        url = f"{model.base_url}/messages" if model.supports_anthropic_format else f"{model.base_url}/chat/completions"
        print(f"[ROUTING] {provider_name} -> {model.model} ({url})")
        print(f"[DEBUG] Request model field: '{body.get('model', 'NOT SET')}'")

        # Prepare request body
        if model.supports_anthropic_format:
            body = data.copy()
            body["model"] = model.model
            print(f"[DEBUG] Sending to {provider_name}: model='{model.model}'")
            # Hapus parameter yang tidak didukung
            for key in ["stream_options"]:
                body.pop(key, None)
        else:
            # OpenAI format
            body = self._transform_to_openai(data)
            body["model"] = model.model
            print(f"[DEBUG] Sending to {provider_name}: model='{model.model}'")
            # Hapus parameter yang tidak didukung untuk Konektika
            for key in ["temperature", "top_k", "top_p", "seed"]:
                body.pop(key, None)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(url, json=body, headers=headers)
                print(f"[DEBUG] {provider_name} response status: {response.status_code}")
                response.raise_for_status()
                result = response.json()
                print(f"[DEBUG] {provider_name} response keys: {list(result.keys())}")
            except httpx.HTTPStatusError as e:
                error_body = e.response.text[:500]
                print(f"[ERROR] {provider_name} HTTP {e.response.status_code}: {error_body}")
                raise

            # Transform response kalau perlu
            if not model.supports_anthropic_format and is_anthropic_format:
                result = self._transform_from_openai(result, "anthropic")

            # Override model name dengan exposed name
            result["model"] = self.exposed_model_name

            return result

    async def _stream_model(
        self,
        model: ModelConfig,
        data: dict,
        is_anthropic_format: bool
    ) -> AsyncGenerator[str, None]:
        """Streaming request ke model"""
        headers = {
            "Authorization": f"Bearer {model.api_key}",
            "Content-Type": "application/json"
        }

        timeout = httpx.Timeout(self.settings.request_timeout, connect=10.0)

        # Tentukan provider name untuk logging
        provider_name = "Konektika" if "konektika" in model.base_url.lower() else \
                        "DataByte" if "databyte" in model.base_url.lower() else \
                        "GLM" if "glm" in model.base_url.lower() else model.base_url
        
        print(f"[ROUTING] {provider_name} -> {model.model} (STREAM)")

        url = f"{model.base_url}/messages" if model.supports_anthropic_format else f"{model.base_url}/chat/completions"
        body = data.copy() if model.supports_anthropic_format else self._transform_to_openai(data)
        body["model"] = model.model
        body["stream"] = True
        
        print(f"[DEBUG] Sending to {provider_name}: model='{model.model}', stream=True")
        print(f"[DEBUG] Request body keys: {list(body.keys())}")
        print(f"[DEBUG] Messages count: {len(body.get('messages', []))}")

        # Hapus parameter yang tidak didukung
        if not model.supports_anthropic_format:
            for key in ["temperature", "top_k", "top_p", "seed"]:
                body.pop(key, None)
        else:
            body.pop("stream_options", None)

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("POST", url, json=body, headers=headers) as response:
                    print(f"[DEBUG] {provider_name} stream response status: {response.status_code}")
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            # Override model name di stream chunk
                            if data_str and data_str not in ("[DONE]", ""):
                                try:
                                    import json
                                    chunk = json.loads(data_str)
                                    if "model" in chunk:
                                        chunk["model"] = self.exposed_model_name
                                    data_str = json.dumps(chunk)
                                except:
                                    pass
                        yield data_str
                    elif line:
                        yield line
            except httpx.HTTPStatusError as e:
                error_body = e.response.text[:500]
                print(f"[ERROR] {provider_name} stream HTTP {e.response.status_code}: {error_body}")
                raise

    async def handle_request(self, data: dict, is_anthropic_format: bool):
        """Handle request dengan round-robin dan retry"""
        if data.get("stream"):
            # Use yield from for async generator
            async for chunk in self._handle_stream_request(data, is_anthropic_format):
                yield chunk
            return

        # Non-streaming request - collect result then yield
        tried_models = []

        for _ in range(len(self.models) * self.settings.max_retries):
            model = self._get_next_model()

            # Skip kalau udah dicoba semua
            if len(tried_models) >= len(self.models):
                break

            try:
                result = await self._call_model(model, data, is_anthropic_format)
                yield result
                return
            except (httpx.TimeoutException, httpx.HTTPStatusError) as e:
                tried_models.append(model.model)
                print(f"[WARNING] Model {model.model} gagal: {type(e).__name__}")
                continue

        raise Exception(f"Semua model gagal setelah {len(tried_models)} percobaan")

    async def _handle_stream_request(self, data: dict, is_anthropic_format: bool) -> AsyncGenerator[str, None]:
        """Handle streaming request: coba stream → retry non-streaming → failover ke model lain"""
        all_models = self.models.copy()
        current_idx = 0
        
        while current_idx < len(all_models):
            model = all_models[current_idx]
            provider_name = "Konektika" if "konektika" in model.base_url.lower() else \
                            "DataByte" if "databyte" in model.base_url.lower() else \
                            "GLM" if "glm" in model.base_url.lower() else model.base_url
            
            # Step 1: Coba streaming dulu
            print(f"[ROUTING] {provider_name} -> {model.model} (STREAM)")
            try:
                async for chunk in self._stream_model(model, data, is_anthropic_format):
                    yield chunk
                return  # Success
            except httpx.HTTPStatusError as e:
                print(f"[WARNING] Stream {model.model} HTTP {e.response.status_code}: {e.response.text[:200]}")
            except Exception as stream_err:
                err_detail = str(stream_err)[:150]
                print(f"[WARNING] Stream {model.model} gagal: {type(stream_err).__name__} - {err_detail}")
            
            # Step 2: Stream gagal → retry model yang sama tapi non-streaming
            print(f"[ROUTING] {provider_name} -> {model.model} (RETRY NON-STREAM)")
            try:
                result = await self._call_model(model, data, is_anthropic_format)
                # Convert non-stream response ke stream format
                if isinstance(result, dict) and result.get("type") == "message":
                    # Anthropic format
                    content = result.get("content", "")
                    chunk_data = {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": content}
                    }
                    yield json.dumps(chunk_data)
                    yield "data: {\"type\": \"message_stop\"}\n\n"
                elif isinstance(result, dict) and result.get("choices"):
                    # OpenAI format
                    content = result["choices"][0]["message"]["content"]
                    chunk_data = {
                        "type": "content_block_delta",
                        "index": 0,
                        "delta": {"type": "text_delta", "text": content}
                    }
                    yield json.dumps(chunk_data)
                    yield "data: {\"type\": \"message_stop\"}\n\n"
                return  # Success
            except Exception as non_stream_err:
                err_detail = str(non_stream_err)[:150]
                print(f"[WARNING] Non-stream {model.model} juga gagal: {type(non_stream_err).__name__} - {err_detail}")
            
            # Step 3: Gagal total → failover ke model berikutnya
            current_idx += 1
            continue
        
        raise Exception("Semua model gagal setelah coba stream dan non-stream")