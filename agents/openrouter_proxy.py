"""
Guardian Angel — OpenRouter Translation Proxy

A local reverse proxy that intercepts Gemini-API-format requests from the Go localharness
binary and translates them to OpenAI-format requests sent to OpenRouter.
It then translates the responses back to the Gemini-API format.

This allows the Google Antigravity SDK (which expects a Gemini-compatible endpoint)
to work seamlessly with OpenRouter and any custom models.
"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, List, Optional
import httpx
from fastapi import FastAPI, Request, Response, HTTPException
import uvicorn

logger = logging.getLogger("openrouter_proxy")

app = FastAPI(title="Guardian Angel OpenRouter Proxy")

# Load configuration from environment
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-001")

def _normalize_json_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively convert uppercase types (OBJECT, STRING) to lowercase (object, string)."""
    new_schema = {}
    for k, v in schema.items():
        if k == "type" and isinstance(v, str):
            new_schema[k] = v.lower()
        elif isinstance(v, dict):
            new_schema[k] = _normalize_json_schema(v)
        elif isinstance(v, list):
            new_schema[k] = [
                _normalize_json_schema(item) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            new_schema[k] = v
    return new_schema

def _translate_tools(gemini_tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Translate Gemini tools to OpenAI/OpenRouter format."""
    openai_tools = []
    for tool in gemini_tools:
        if "functionDeclarations" in tool:
            for decl in tool["functionDeclarations"]:
                param = decl.get("parameters", {})
                if param:
                    param = _normalize_json_schema(param)
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": decl["name"],
                        "description": decl.get("description", ""),
                        "parameters": param
                    }
                })
    return openai_tools

def _translate_messages(gemini_contents: List[Dict[str, Any]], system_instruction: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Translate Gemini contents to OpenAI/OpenRouter messages list."""
    messages = []
    
    # 1. System instructions first
    if system_instruction and "parts" in system_instruction:
        parts = system_instruction["parts"]
        if parts and "text" in parts[0]:
            messages.append({"role": "system", "content": parts[0]["text"]})
            
    # 2. Iterate through contents
    for idx, content in enumerate(gemini_contents):
        role = content.get("role")
        if role == "model":
            role = "assistant"
        elif not role:
            role = "user"
            
        parts = content.get("parts", [])
        for part in parts:
            if "text" in part:
                messages.append({"role": role, "content": part["text"]})
            elif "functionCall" in part:
                # Assistant calling a tool
                fc = part["functionCall"]
                messages.append({
                    "role": "assistant",
                    "tool_calls": [{
                        "id": f"call_{idx}",
                        "type": "function",
                        "function": {
                            "name": fc["name"],
                            "arguments": json.dumps(fc.get("args", {}))
                        }
                    }]
                })
            elif "functionResponse" in part:
                # Tool returning result
                fr = part["functionResponse"]
                messages.append({
                    "role": "tool",
                    "tool_call_id": f"call_{idx-1}",  # Match corresponding call
                    "name": fr["name"],
                    "content": json.dumps(fr.get("response", {}))
                })
                
    return messages

@app.post("/v1beta/models/{model_name}:generateContent")
@app.post("/v1/models/{model_name}:generateContent")
async def generate_content(model_name: str, request: Request):
    """Intercept Gemini generateContent request and proxy it to OpenRouter."""
    if not OPENROUTER_API_KEY:
        logger.error("OPENROUTER_API_KEY not configured")
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY environment variable is missing.")
        
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")
        
    # Translate contents and system instruction
    contents = body.get("contents", [])
    system_instruction = body.get("systemInstruction")
    messages = _translate_messages(contents, system_instruction)
    
    # Translate tools
    gemini_tools = body.get("tools", [])
    openai_tools = _translate_tools(gemini_tools)
    
    # Build OpenRouter payload
    payload: Dict[str, Any] = {
        "model": OPENROUTER_MODEL,
        "messages": messages
    }
    
    if openai_tools:
        payload["tools"] = openai_tools
        # Enable auto choice
        payload["tool_choice"] = "auto"
        
    # Translate generationConfig
    generation_config = body.get("generationConfig", {})
    if generation_config.get("responseMimeType") == "application/json":
        payload["response_format"] = {"type": "json_object"}
        # If schema is present, we can append a guiding instruction or append to prompt
        
    if "temperature" in generation_config:
        payload["temperature"] = generation_config["temperature"]
    if "maxOutputTokens" in generation_config:
        payload["max_tokens"] = generation_config["maxOutputTokens"]
        
    logger.info("Proxying request for model %s -> OpenRouter model %s", model_name, OPENROUTER_MODEL)
    
    # Dispatch HTTP call to OpenRouter
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/google/antigravity",
        "X-Title": "Guardian Angel Protection Shield"
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            res_data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("OpenRouter HTTP Error: %s - Response: %s", str(e), e.response.text)
            raise HTTPException(status_code=e.response.status_code, detail=f"OpenRouter error: {e.response.text}")
        except Exception as e:
            logger.error("OpenRouter connection failed: %s", str(e))
            raise HTTPException(status_code=502, detail=f"Failed to reach OpenRouter: {str(e)}")
            
    # Translate OpenAI response back to Gemini format
    choices = res_data.get("choices", [])
    if not choices:
        raise HTTPException(status_code=502, detail="Empty response choices from OpenRouter")
        
    message = choices[0].get("message", {})
    parts = []
    
    if message.get("content"):
        parts.append({"text": message["content"]})
        
    if message.get("tool_calls"):
        for tc in message["tool_calls"]:
            func = tc.get("function", {})
            try:
                args = json.loads(func.get("arguments", "{}"))
            except Exception:
                args = {}
            parts.append({
                "functionCall": {
                    "name": func.get("name"),
                    "args": args
                }
            })
            
    # If no content and no tool calls, return empty text
    if not parts:
        parts.append({"text": ""})
        
    gemini_response = {
        "candidates": [{
            "content": {
                "role": "model",
                "parts": parts
            },
            "finishReason": "STOP"
        }]
    }
    
    return Response(content=json.dumps(gemini_response), media_type="application/json")

# Background thread server management
proxy_task: Optional[asyncio.Task] = None
proxy_port: int = 8085

def start_proxy_thread():
    """Start the proxy server in a background event loop or thread if needed."""
    config = uvicorn.Config(app, host="127.0.0.1", port=proxy_port, log_level="warning")
    server = uvicorn.Server(config)
    
    # If there is already a running loop, create a task
    try:
        loop = asyncio.get_running_loop()
        global proxy_task
        proxy_task = loop.create_task(server.serve())
        logger.info("Proxy server started as background task on port %s", proxy_port)
    except RuntimeError:
        # No running loop, run synchronously (useful for test scripts)
        logger.info("Starting proxy server synchronously on port %s", proxy_port)
        server.run()

if __name__ == "__main__":
    start_proxy_thread()
