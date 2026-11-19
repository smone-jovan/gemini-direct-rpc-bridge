"""
Gemini Direct RPC Bridge - Pure HTTP Bridge for Google Gemini Web (Metode 2)
Zero browser needed! 100% background HTTP RPC.
Supports:
- Multi-Session Isolation (Stateless Execution vs Stateful Chat via session_id)
- Extended Thinking Toggle (thinking_level: high/low or extended_thinking: true/false)
- Native Model Selection: gemini-carbon, gemini-neon (4 Neon / Deeper analysis), gemini-4-hydrogen, gemini-auto
- Server-Sent Events (SSE) Real-Time Streaming (stream: true)
- High-Performance orjson serialization with fallback
- OpenAI-compatible API at http://127.0.0.1:8765/v1
"""

import asyncio
import time
import os
import sys
import uuid
import json
import hashlib
from typing import Optional, Dict, AsyncGenerator
from collections import OrderedDict
from gemini_webapi import GeminiClient, ChatSession
from gemini_webapi.types.modeloutput import ModelOutput
from gemini_webapi.types.availablemodel import AvailableModel

# Ultra-fast JSON serialization with fallback
try:
    import orjson

    def json_dumps(obj, indent: bool = False) -> bytes:
        if indent:
            return orjson.dumps(obj, option=orjson.OPT_INDENT_2)
        return orjson.dumps(obj)

    def json_loads(data):
        return orjson.loads(data)
except ImportError:
    def json_dumps(obj, indent: bool = False) -> bytes:
        if indent:
            return json.dumps(obj, indent=2).encode("utf-8")
        return json.dumps(obj).encode("utf-8")

    def json_loads(data):
        if isinstance(data, (bytes, bytearray)):
            return json.loads(data.decode("utf-8"))
        return json.loads(data)


HTTP_HOST = "127.0.0.1"
HTTP_PORT = 8765
MAX_SESSIONS = 100
MAX_BODY_BYTES = 2 * 1024 * 1024  # Maksimum payload 2 MB (OOM Protection)
READ_TIMEOUT = 10.0               # Timeout pembacaan socket (Slowloris Protection)

CORS_HEADERS = (
    "Access-Control-Allow-Origin: *\r\n"
    "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
    "Access-Control-Allow-Headers: Content-Type, Authorization\r\n"
)

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "cookies.json")
gemini_client: Optional[GeminiClient] = None
active_sessions: OrderedDict[str, ChatSession] = OrderedDict()
init_lock = asyncio.Lock()
session_lock = asyncio.Lock()


def load_cookies() -> dict:
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
        print("[Bridge Error] Cookies not found in cookies.json or GEMINI_SECURE_1PSID env var!", flush=True)
        return

    print("[Bridge] Menginisialisasi GeminiClient via HTTP RPC...", flush=True)
    gemini_client = GeminiClient(
        secure_1psid=psid,
        secure_1psidts=psidts,
        auto_refresh=True
    )
    await gemini_client.init()

    # Registrasi & Pemetaan Model 4 Neon (Deeper analysis - Neon4p0 dengan model_number: 3)
    try:
        neon_model = gemini_client.resolve_model("neon")
        if neon_model:
            gemini_client._model_registry["gemini-neon"] = neon_model
            gemini_client._model_registry["gemini-4-neon"] = neon_model
            gemini_client._model_registry["neon"] = neon_model
            # Backward-compatibility alias: argon -> neon
            gemini_client._model_registry["gemini-4-argon"] = neon_model
            gemini_client._model_registry["argon"] = neon_model
    except Exception as e:
        print(f"[Bridge Warning] Model Neon tidak ditemukan di RPC registry: {e}", flush=True)

    # Registrasi & Pemetaan Model 4 Carbon (Code & complex work - model_number: 8)
    try:
        carbon_model = gemini_client.resolve_model("carbon")
        if carbon_model:
            gemini_client._model_registry["gemini-carbon"] = carbon_model
            gemini_client._model_registry["carbon"] = carbon_model
    except Exception as e:
        print(f"[Bridge Warning] Model Carbon tidak ditemukan di RPC registry: {e}", flush=True)

    # Bersihkan sisa alias lama yang sudah tidak valid
    gemini_client._model_registry.pop("gemini-pro", None)
    gemini_client._model_registry.pop("pro", None)

    print("[Bridge] Terhubung sukses ke Google Gemini! (100% Bebas Browser | 4 Neon Aktif Model# 3 | 4 Carbon Aktif Model# 8 | 4 Hydrogen Aktif Model# 1 | Auto Aktif Model# 6)", flush=True)


async def ensure_client() -> GeminiClient:
    global gemini_client
    if not gemini_client:
        async with init_lock:
            if not gemini_client:
                await init_client()
    if not gemini_client:
        raise RuntimeError("Gagal menginisialisasi GeminiClient. Periksa cookies.json atau environment variables.")
    return gemini_client


def resolve_target_model(model_name: Optional[str], mode: str = "chat") -> tuple[str, str]:
    raw = (model_name or "").lower().strip()
    
    # Auto-detect mode from model suffix e.g. "gemini-neon:task", "neon:task", "argon:task"
    if ":task" in raw:
        mode = "task"
        raw = raw.replace(":task", "").strip()
    elif ":chat" in raw:
        mode = "chat"
        raw = raw.replace(":chat", "").strip()
        
    target = raw

    # MODE TASK (Resmi Google Project Remy: 4 Neon, 4 Carbon & 4 Hydrogen)
    if mode == "task":
        if any(k in target for k in ["carbon", "complex"]):
            return "gemini-carbon", "task"
        if any(k in target for k in ["hydrogen", "everyday", "fast"]):
            return "gemini-4-hydrogen", "task"
        # Default task model: gemini-neon (mendukung 'neon', 'argon', 'code', 'analysis', 'dev', 'prog', 'deeper')
        return "gemini-neon", "task"

    # MODE CHAT: HIERARKI MUTLAK: Carbon > Neon > Hydrogen > Auto (dengan alias Argon -> Neon)
    if any(k in target for k in ["carbon", "complex"]):
        return "gemini-carbon", "chat"
    elif any(k in target for k in ["neon", "argon", "deeper", "analysis", "code", "dev"]):
        return "gemini-neon", "chat"
    elif any(k in target for k in ["hydrogen", "everyday", "fast"]):
        return "gemini-4-hydrogen", "chat"
    elif any(k in target for k in ["auto", "adapt"]):
        return "gemini-auto", "chat"
    elif any(k in target for k in ["flash", "lite", "quick"]):
        return "gemini-auto", "chat"

    # Default umum: gemini-neon
    return "gemini-neon", "chat"


def extract_text_from_content(content) -> str:
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts)
    return str(content) if content is not None else ""


async def get_or_create_session(session_id: str, target_model: str) -> ChatSession:
    client = await ensure_client()
    async with session_lock:
        if session_id in active_sessions:
            active_sessions.move_to_end(session_id)
            chat = active_sessions[session_id]
            if target_model and chat.model != target_model:
                chat.model = target_model
        else:
            if len(active_sessions) >= MAX_SESSIONS:
                evicted_id, _ = active_sessions.popitem(last=False)
                print(f"[Bridge] Menggusur sesi tidak aktif (LRU): {evicted_id}", flush=True)
            # Jika session_id adalah Google CID asli (c_...), lampirkan langsung ke thread tersebut!
            cid_param = session_id if session_id.startswith("c_") else ""
            chat = client.start_chat(model=target_model, cid=cid_param)
            active_sessions[session_id] = chat
        return chat


async def ask_gemini(
    prompt: str,
    model: str = "gemini-neon",
    session_id: Optional[str] = None,
    extended_thinking: bool = False,
    mode: str = "chat"
) -> str:
    client = await ensure_client()
    target_model, effective_mode = resolve_target_model(model, mode=mode)
    # Di mode TASK resmi Google, thinking toggle ditiadakan (penalaran agentic otomatis di backend)
    actual_thinking = False if effective_mode == "task" else extended_thinking
    is_task = (effective_mode == "task")
    print(f"[Bridge] Mode: {effective_mode.upper()} | Model: '{target_model}' (Session: {session_id or 'Single-turn'}, Thinking: {actual_thinking}, RemyTask: {is_task})...", flush=True)

    if session_id:
        chat = await get_or_create_session(session_id, target_model)
        response = await chat.send_message(prompt, extended_thinking=actual_thinking, task_mode=is_task)
        return response.text

    response = await client.generate_content(
        prompt,
        model=target_model,
        extended_thinking=actual_thinking,
        task_mode=is_task
    )
    return response.text


async def ask_gemini_stream(
    prompt: str,
    model: str = "gemini-neon",
    session_id: Optional[str] = None,
    extended_thinking: bool = False,
    mode: str = "chat"
) -> AsyncGenerator[ModelOutput, None]:
    client = await ensure_client()
    target_model, effective_mode = resolve_target_model(model, mode=mode)
    actual_thinking = False if effective_mode == "task" else extended_thinking
    is_task = (effective_mode == "task")
    print(f"[Bridge] Mode: {effective_mode.upper()} (Stream) | Model: '{target_model}' (Session: {session_id or 'Single-turn'}, Thinking: {actual_thinking}, RemyTask: {is_task})...", flush=True)

    if session_id:
        chat = await get_or_create_session(session_id, target_model)
        async for chunk in chat.send_message_stream(prompt, extended_thinking=actual_thinking, task_mode=is_task):
            yield chunk
    else:
        async for chunk in client.generate_content_stream(
            prompt,
            model=target_model,
            extended_thinking=actual_thinking,
            task_mode=is_task
        ):
            yield chunk


async def close_writer(writer: asyncio.StreamWriter):
    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass


async def send_json_response(
    writer: asyncio.StreamWriter,
    status_code: int,
    status_text: str,
    data: dict,
    indent: bool = False
):
    res_bytes = json_dumps(data, indent=indent)
    response = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: application/json; charset=utf-8\r\n"
        f"Content-Length: {len(res_bytes)}\r\n"
        f"{CORS_HEADERS}\r\n"
    ).encode("utf-8") + res_bytes
    writer.write(response)
    await writer.drain()


async def http_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        header_lines = []
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=READ_TIMEOUT)
            if not line or line == b"\r\n":
                break
            header_lines.append(line.decode("utf-8", errors="replace"))

        if not header_lines:
            await close_writer(writer)
            return

        request_line = header_lines[0].strip().split()
        if len(request_line) < 2:
            await close_writer(writer)
            return

        method, raw_path = request_line[0].upper(), request_line[1]
        clean_path = raw_path.split("?")[0].rstrip("/")
        if not clean_path:
            clean_path = "/"

        if method == "OPTIONS":
            response = f"HTTP/1.1 204 No Content\r\n{CORS_HEADERS}\r\n".encode("utf-8")
            writer.write(response)
            await writer.drain()
            await close_writer(writer)
            return

        content_length = 0
        for h in header_lines[1:]:
            if h.lower().startswith("content-length:"):
                try:
                    content_length = int(h.split(":", 1)[1].strip())
                except ValueError:
                    content_length = 0
                break

        if content_length > MAX_BODY_BYTES:
            await send_json_response(writer, 413, "Payload Too Large", {
                "error": {"message": "Payload Terlalu Besar (Max 2MB)", "type": "payload_too_large"}
            })
            await close_writer(writer)
            return

        body = b""
        if content_length > 0:
            body = await asyncio.wait_for(reader.readexactly(content_length), timeout=READ_TIMEOUT)

        if clean_path in ["/health", "/"]:
            status_obj = {
                "status": "online",
                "mode": "Direct HTTP RPC (Metode 2 - Tanpa Browser)",
                "client_initialized": gemini_client is not None,
                "gemini_ui_modes": ["chat", "task"],
                "task_models": [
                    "Deeper analysis (4 Neon - Model# 3)",
                    "Code & complex work (4 Carbon - Model# 8)",
                    "Everyday help (4 Hydrogen - Model# 1)"
                ],
                "active_sessions": list(active_sessions.keys()),
                "capabilities": {
                    "task_mode": "Agentic task execution (4 Neon, 4 Carbon & 4 Hydrogen) without manual thinking toggle",
                    "chat_mode": "Full conversational models with optional thinking toggles",
                    "session_isolation": True,
                    "streaming": True,
                    "orjson_accelerated": "orjson" in sys.modules
                },
                "supported_models": [
                    "gemini-carbon",
                    "gemini-neon",
                    "gemini-4-neon",
                    "gemini-4-argon (alias to neon)",
                    "gemini-4-hydrogen",
                    "gemini-auto"
                ],
                "endpoint": f"http://{HTTP_HOST}:{HTTP_PORT}/v1/chat/completions"
            }
            await send_json_response(writer, 200, "OK", status_obj, indent=True)
            await close_writer(writer)
            return

        if clean_path == "/v1/models" and method == "GET":
            models_obj = {
                "object": "list",
                "data": [
                    {"id": "gemini-carbon", "object": "model", "owned_by": "google-deepmind", "description": "Code & complex work (4 Carbon - Model# 8)", "modes": ["chat", "task"]},
                    {"id": "gemini-neon", "object": "model", "owned_by": "google-deepmind", "description": "Deeper analysis (4 Neon - Model# 3)", "modes": ["chat", "task"]},
                    {"id": "gemini-4-neon", "object": "model", "owned_by": "google-deepmind", "description": "Deeper analysis (4 Neon - Model# 3)", "modes": ["chat", "task"]},
                    {"id": "gemini-4-argon", "object": "model", "owned_by": "google-deepmind", "description": "Backward-compatibility alias for 4 Neon", "modes": ["chat", "task"]},
                    {"id": "gemini-4-hydrogen", "object": "model", "owned_by": "google-deepmind", "description": "Everyday help (4 Hydrogen - Model# 1)", "modes": ["chat", "task"]},
                    {"id": "gemini-auto", "object": "model", "owned_by": "google-deepmind", "description": "Adapts to your needs (Auto - Model# 6)", "modes": ["chat"]}
                ]
            }
            await send_json_response(writer, 200, "OK", models_obj)
            await close_writer(writer)
            return

        if clean_path == "/v1/chat/completions" and method == "POST":
            try:
                try:
                    req_json = json_loads(body)
                except Exception as e:
                    await send_json_response(writer, 400, "Bad Request", {
                        "error": {"message": f"Malformed JSON payload: {e}", "type": "invalid_request_error"}
                    })
                    await close_writer(writer)
                    return

                messages = req_json.get("messages")
                if not messages or not isinstance(messages, list):
                    await send_json_response(writer, 400, "Bad Request", {
                        "error": {"message": "'messages' is a required non-empty array", "type": "invalid_request_error"}
                    })
                    await close_writer(writer)
                    return

                model = req_json.get("model", "gemini-neon")
                mode = str(req_json.get("mode", "chat")).lower().strip()
                if mode not in ["task", "chat"]:
                    mode = "chat"

                resolved_model, effective_mode = resolve_target_model(model, mode=mode)
                session_id = req_json.get("session_id") or req_json.get("conversation_id")
                is_stateless = bool(req_json.get("stateless", False))
                is_stream = bool(req_json.get("stream", False))

                # AUTO-SESSION & STICKY CONTINUATION:
                # Default bridge adalah STATEFUL / BERSAMBUNG (bukan stateless terpecah-pecah!)
                if not session_id and not is_stateless:
                    if len(messages) > 1:
                        # Jika klien mengirim riwayat pesan multi-turn, turunkan ID sesi dari seed (system + user)
                        seed_parts = [
                            f"{m.get('role')}:{extract_text_from_content(m.get('content', '')).strip()}"
                            for m in messages
                            if m.get("role") in ("system", "user")
                        ][:2]
                        if seed_parts:
                            raw_seed = "|".join(seed_parts).encode("utf-8")
                            session_id = f"auto-{hashlib.sha256(raw_seed).hexdigest()[:16]}"
                    else:
                        # Jika pesan tunggal dikirim berurutan, gunakan sticky session default
                        # agar obrolan otomatis bersambung di thread yang sama pada Google Gemini!
                        session_id = f"sticky-{effective_mode}-session"

                # Check thinking level
                thinking_level = req_json.get("thinking_level") or req_json.get("reasoning_effort")
                extended_thinking = (
                    bool(req_json.get("extended_thinking", False)) or
                    str(thinking_level).lower() in ["high", "extended", "tinggi", "true", "1"]
                )

                # Ekstraksi prompt:
                # Hanya kirim pesan user paling akhir JIKA sesi sudah aktif di memori bridge!
                # Jika turn pertama atau sesi belum terinisialisasi di LRU, kirim full context untuk bootstrapping thread.
                if session_id and session_id in active_sessions:
                    prompt = extract_text_from_content(messages[-1].get("content", ""))
                elif len(messages) == 1:
                    prompt = extract_text_from_content(messages[0].get("content", ""))
                else:
                    parts = []
                    for m in messages:
                        role = m.get("role", "user")
                        content = extract_text_from_content(m.get("content", ""))
                        if role == "system":
                            parts.append(f"[System Instruction]: {content}")
                        elif role == "user":
                            parts.append(f"User: {content}")
                        elif role == "assistant":
                            parts.append(f"Assistant: {content}")
                    prompt = "\n\n".join(parts) + "\n\nAssistant:"

                if not prompt.strip():
                    await send_json_response(writer, 400, "Bad Request", {
                        "error": {"message": "Prompt content cannot be empty", "type": "invalid_request_error"}
                    })
                    await close_writer(writer)
                    return

                completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
                created_ts = int(time.time())

                if is_stream:
                    headers = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/event-stream; charset=utf-8\r\n"
                        "Cache-Control: no-cache\r\n"
                        "Connection: keep-alive\r\n"
                        f"{CORS_HEADERS}\r\n"
                    ).encode("utf-8")
                    writer.write(headers)
                    await writer.drain()

                    # First role chunk
                    first_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": resolved_model,
                        "choices": [{
                            "index": 0,
                            "delta": {"role": "assistant", "content": ""},
                            "finish_reason": None
                        }]
                    }
                    writer.write(b"data: " + json_dumps(first_chunk) + b"\n\n")
                    await writer.drain()

                    async for chunk in ask_gemini_stream(
                        prompt,
                        model=resolved_model,
                        session_id=session_id,
                        extended_thinking=extended_thinking,
                        mode=effective_mode
                    ):
                        delta = chunk.text_delta
                        if delta:
                            chunk_obj = {
                                "id": completion_id,
                                "object": "chat.completion.chunk",
                                "created": created_ts,
                                "model": resolved_model,
                                "choices": [{
                                    "index": 0,
                                    "delta": {"content": delta},
                                    "finish_reason": None
                                }]
                            }
                            writer.write(b"data: " + json_dumps(chunk_obj) + b"\n\n")
                            await writer.drain()

                    stop_chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": created_ts,
                        "model": resolved_model,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop"
                        }]
                    }
                    writer.write(b"data: " + json_dumps(stop_chunk) + b"\n\ndata: [DONE]\n\n")
                    await writer.drain()
                    await close_writer(writer)
                    return

                # Non-streaming response
                resp_text = await ask_gemini(
                    prompt,
                    model=resolved_model,
                    session_id=session_id,
                    extended_thinking=extended_thinking,
                    mode=effective_mode
                )

                openai_resp = {
                    "id": completion_id,
                    "object": "chat.completion",
                    "created": created_ts,
                    "model": resolved_model,
                    "mode": effective_mode,
                    "session_id": session_id,
                    "conversation_id": (active_sessions[session_id].cid if session_id and session_id in active_sessions else None),
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
                await send_json_response(writer, 200, "OK", openai_resp)
                await close_writer(writer)
                return

            except Exception as e:
                err_body = {
                    "error": {
                        "message": str(e),
                        "type": "bridge_error"
                    }
                }
                await send_json_response(writer, 500, "Internal Server Error", err_body)
                await close_writer(writer)
                return

        await send_json_response(writer, 404, "Not Found", {"error": "Not Found"})
        await close_writer(writer)

    except Exception as e:
        print(f"[HTTP Error] {e}", flush=True)
        await close_writer(writer)


async def main():
    print("=" * 60, flush=True)
    print("  🚀 GEMINI DIRECT RPC BRIDGE (Metode 2 - 100% Tanpa Browser)", flush=True)
    print("=" * 60, flush=True)
    print(f"[*] OpenAI API Server: http://{HTTP_HOST}:{HTTP_PORT}/v1", flush=True)
    print(f"[*] Health Check     : http://{HTTP_HOST}:{HTTP_PORT}/health", flush=True)
    print("=" * 60, flush=True)

    server = await asyncio.start_server(http_handler, HTTP_HOST, HTTP_PORT)
    print(f"[*] Socket listening on http://{HTTP_HOST}:{HTTP_PORT}. Inisialisasi Google client...", flush=True)

    try:
        await init_client()
    except Exception as e:
        print(f"[Bridge Warning] Inisialisasi awal client gagal: {e}", flush=True)

    await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Bridge] Server dimatikan.")
