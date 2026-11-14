"""
Gemini Direct RPC Bridge - Pure HTTP Bridge for Google Gemini Web (Metode 2)
Zero browser needed! 100% background HTTP RPC.
Supports:
- Multi-Session Isolation (Chat vs Task via session_id)
- Extended Thinking Toggle (thinking_level: high/low or extended_thinking: true/false)
- Native Model Selection: gemini-4-hydrogen, gemini-pro (Argon), gemini-flash-lite
- OpenAI-compatible API at http://127.0.0.1:8765/v1
"""

import asyncio
import json
import time
import os
import sys
import uuid
from typing import Optional, Dict
from collections import OrderedDict
from gemini_webapi import GeminiClient, ChatSession

HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8765
MAX_SESSIONS = 100
MAX_BODY_BYTES = 2 * 1024 * 1024  # Maksimum payload 2 MB (OOM Protection)
READ_TIMEOUT = 10.0               # Timeout pembacaan socket (Slowloris Protection)

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "cookies.json")
gemini_client: Optional[GeminiClient] = None
active_sessions: OrderedDict[str, ChatSession] = OrderedDict()
init_lock = asyncio.Lock()

def load_cookies():
    data = {}
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[Bridge Warning] Could not parse {COOKIE_FILE}: {e}", flush=True)
    if not data.get("__Secure-1PSID"):
        env_psid = os.environ.get("GEMINI_SECURE_1PSID")
        env_psidts = os.environ.get("GEMINI_SECURE_1PSIDTS")
        if env_psid:
            data["__Secure-1PSID"] = env_psid
            if env_psidts:
                data["__Secure-1PSIDTS"] = env_psidts
    return data

async def init_client():
    global gemini_client
    cookies = load_cookies()
    psid = cookies.get("__Secure-1PSID")
    psidts = cookies.get("__Secure-1PSIDTS")

    if not psid:
        print("[Bridge Error] Cookies not found in cookies.json!", flush=True)
        return

    print("[Bridge] Menginisialisasi GeminiClient via HTTP RPC...", flush=True)
    gemini_client = GeminiClient(
        secure_1psid=psid,
        secure_1psidts=psidts,
        auto_refresh=True
    )
    await gemini_client.init()
    print("[Bridge] Terhubung sukses ke Google Gemini! (100% Bebas Browser)", flush=True)

def resolve_target_model(model_name: str) -> str:
    target = model_name.lower().strip()
    if "hydrogen" in target or "fast" in target:
        return "gemini-4-hydrogen"
    elif "argon" in target or "pro" in target or "research" in target:
        return "gemini-pro"
    elif "carbon" in target:
        return "gemini-carbon"
    elif "flash" in target:
        return "gemini-flash-lite"
    return "gemini-pro"

async def ask_gemini(
    prompt: str, 
    model: str = "gemini-pro", 
    session_id: Optional[str] = None, 
    extended_thinking: bool = False
) -> str:
    global gemini_client, active_sessions
    if not gemini_client:
        async with init_lock:
            if not gemini_client:
                await init_client()
    if not gemini_client:
        raise RuntimeError("Gagal menginisialisasi GeminiClient. Periksa cookies.json.")

    target_model = resolve_target_model(model)
    print(f"[Bridge] Mengirim prompt ke '{target_model}' (Session: {session_id or 'Stateless/Task'}, Thinking: {extended_thinking})...", flush=True)

    # Mode Chat Berkelanjutan (LRU Eviction Policy)
    if session_id:
        if session_id in active_sessions:
            active_sessions.move_to_end(session_id)
        else:
            if len(active_sessions) >= MAX_SESSIONS:
                evicted_id, _ = active_sessions.popitem(last=False)
                print(f"[Bridge] Menggusur sesi tidak aktif (LRU): {evicted_id}", flush=True)
            active_sessions[session_id] = gemini_client.start_chat(model=target_model)
        
        chat = active_sessions[session_id]
        response = await chat.send_message(prompt)
        return response.text

    # Mode Task Mandiri / Stateless
    response = await gemini_client.generate_content(
        prompt, 
        model=target_model, 
        extended_thinking=extended_thinking
    )
    return response.text

async def http_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        header_lines = []
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=READ_TIMEOUT)
            if not line or line == b"\r\n":
                break
            header_lines.append(line.decode("utf-8", errors="replace"))

        if not header_lines:
            writer.close()
            return

        request_line = header_lines[0].strip().split()
        if len(request_line) < 2:
            writer.close()
            return

        method, path = request_line[0], request_line[1]

        content_length = 0
        for h in header_lines[1:]:
            if h.lower().startswith("content-length:"):
                content_length = int(h.split(":", 1)[1].strip())
                break

        if content_length > MAX_BODY_BYTES:
            err_body = b'{"error": {"message": "Payload Terlalu Besar (Max 2MB)", "type": "payload_too_large"}}'
            writer.write(f"HTTP/1.1 413 Payload Too Large\r\nContent-Type: application/json\r\nContent-Length: {len(err_body)}\r\n\r\n".encode("utf-8") + err_body)
            await writer.drain()
            writer.close()
            return

        body = b""
        if content_length > 0:
            body = await asyncio.wait_for(reader.readexactly(content_length), timeout=READ_TIMEOUT)

        cors_headers = (
            "Access-Control-Allow-Origin: *\r\n"
            "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
            "Access-Control-Allow-Headers: Content-Type, Authorization\r\n"
        )

        if method == "OPTIONS":
            response = f"HTTP/1.1 204 No Content\r\n{cors_headers}\r\n".encode("utf-8")
            writer.write(response)
            await writer.drain()
            writer.close()
            return

        if path == "/health" or path == "/":
            status_obj = {
                "status": "online",
                "mode": "Direct HTTP RPC (Metode 2 - Tanpa Browser)",
                "client_initialized": gemini_client is not None,
                "active_sessions": list(active_sessions.keys()),
                "capabilities": {
                    "extended_thinking": True,
                    "session_isolation": True,
                    "task_vs_chat": True
                },
                "supported_models": ["gemini-4-hydrogen", "gemini-pro", "gemini-flash-lite"],
                "endpoint": f"http://{HTTP_HOST}:{HTTP_PORT}/v1/chat/completions"
            }
            res_body = json.dumps(status_obj, indent=2).encode("utf-8")
            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(res_body)}\r\n"
                f"{cors_headers}\r\n"
            ).encode("utf-8") + res_body
            writer.write(response)
            await writer.drain()
            writer.close()
            return

        if path == "/v1/models" and method == "GET":
            models_obj = {
                "object": "list",
                "data": [
                    {"id": "gemini-4-hydrogen", "object": "model", "owned_by": "google-deepmind", "description": "Everyday help (Super Fast)"},
                    {"id": "gemini-pro", "object": "model", "owned_by": "google-deepmind", "description": "Detailed research (Argon / Deep Reasoning)"},
                    {"id": "gemini-flash-lite", "object": "model", "owned_by": "google-deepmind", "description": "Quick answers"}
                ]
            }
            res_body = json.dumps(models_obj).encode("utf-8")
            response = (
                f"HTTP/1.1 200 OK\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(res_body)}\r\n"
                f"{cors_headers}\r\n"
            ).encode("utf-8") + res_body
            writer.write(response)
            await writer.drain()
            writer.close()
            return

        if path == "/v1/chat/completions" and method == "POST":
            try:
                req_json = json.loads(body.decode("utf-8"))
                messages = req_json.get("messages", [])
                model = req_json.get("model", "gemini-pro")
                session_id = req_json.get("session_id") or req_json.get("user")
                
                # Check thinking level
                thinking_level = req_json.get("thinking_level") or req_json.get("reasoning_effort")
                extended_thinking = (
                    req_json.get("extended_thinking", False) or 
                    str(thinking_level).lower() in ["high", "extended", "tinggi", "true"]
                )

                if len(messages) == 1:
                    prompt = messages[0].get("content", "")
                else:
                    parts = []
                    for m in messages:
                        role = m.get("role", "user")
                        content = m.get("content", "")
                        if role == "system":
                            parts.append(f"[System Instruction]: {content}")
                        elif role == "user":
                            parts.append(f"User: {content}")
                        elif role == "assistant":
                            parts.append(f"Assistant: {content}")
                    prompt = "\n\n".join(parts) + "\n\nAssistant:"

                resp_text = await ask_gemini(
                    prompt, 
                    model=model, 
                    session_id=session_id, 
                    extended_thinking=extended_thinking
                )

                openai_resp = {
                    "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": resolve_target_model(model),
                    "session_id": session_id,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": resp_text
                            },
                            "finish_reason": "stop"
                        }
                    ],
                    "usage": {
                        "prompt_tokens": len(prompt.split()),
                        "completion_tokens": len(resp_text.split()),
                        "total_tokens": len(prompt.split()) + len(resp_text.split())
                    }
                }

                res_body = json.dumps(openai_resp).encode("utf-8")
                response = (
                    f"HTTP/1.1 200 OK\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(res_body)}\r\n"
                    f"{cors_headers}\r\n"
                ).encode("utf-8") + res_body
                writer.write(response)
                await writer.drain()

            except Exception as e:
                err_body = json.dumps({"error": {"message": str(e), "type": "bridge_error"}}).encode("utf-8")
                response = (
                    f"HTTP/1.1 500 Internal Server Error\r\n"
                    f"Content-Type: application/json\r\n"
                    f"Content-Length: {len(err_body)}\r\n"
                    f"{cors_headers}\r\n"
                ).encode("utf-8") + err_body
                writer.write(response)
                await writer.drain()

            writer.close()
            return

        not_found = b"{\"error\": \"Not Found\"}"
        writer.write(
            f"HTTP/1.1 404 Not Found\r\nContent-Type: application/json\r\nContent-Length: {len(not_found)}\r\n\r\n".encode("utf-8") + not_found
        )
        await writer.drain()
        writer.close()

    except Exception as e:
        print(f"[HTTP Error] {e}")
        try:
            writer.close()
        except:
            pass

async def main():
    print("=" * 60)
    print("  🚀 GEMINI DIRECT RPC BRIDGE (Metode 2 - 100% Tanpa Browser)")
    print("=" * 60)
    print(f"[*] OpenAI API Server: http://{HTTP_HOST}:{HTTP_PORT}/v1")
    print(f"[*] Health Check     : http://{HTTP_HOST}:{HTTP_PORT}/health")
    print("=" * 60)

    await init_client()

    server = await asyncio.start_server(http_handler, HTTP_HOST, HTTP_PORT)
    await server.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Bridge] Server dimatikan.")
