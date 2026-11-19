"""
Gemini Direct RPC Bridge - Pure HTTP Bridge for Google Gemini Web (Metode 2)
Zero browser needed! 100% background HTTP RPC.
Supports:
- Atomic Client Initialization (retry-safe, zero half-initialized state)
- Multi-Session Isolation with Mode Namespace (mode, session_id) & Per-Session Lock
- Extended Thinking Toggle (thinking_level: high/low or extended_thinking: true/false)
- Native Model Selection: gemini-carbon, gemini-neon (4 Neon / Deeper analysis), gemini-4-hydrogen, gemini-auto
- Server-Sent Events (SSE) Real-Time Streaming with Safe Error Framing
- HTTP/1.1 Parser Hardening & Anti-Slowloris Protection
- Optional Local Bearer Token Authentication (BRIDGE_API_KEY)
- High-Performance orjson serialization with fallback
- OpenAI-compatible API at http://127.0.0.1:8765/v1
"""

import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from typing import AsyncGenerator, Dict, Optional, Tuple

from gemini_webapi import ChatSession, GeminiClient
from gemini_webapi.types.modeloutput import ModelOutput

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
MAX_HEADERS = 64                  # Batas jumlah header HTTP (Anti-Header Flood)
HEADER_TOTAL_TIMEOUT = 10.0       # Total timeout pembacaan seluruh header (Anti-Slowloris)
READ_TIMEOUT = 10.0               # Timeout pembacaan body socket

BRIDGE_API_KEY = os.environ.get("BRIDGE_API_KEY", "").strip()

CORS_HEADERS = (
    "Access-Control-Allow-Origin: *\r\n"
    "Access-Control-Allow-Methods: GET, POST, OPTIONS\r\n"
    "Access-Control-Allow-Headers: Content-Type, Authorization\r\n"
)

COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.json")


@dataclass
class SessionEntry:
    chat: ChatSession
    lock: asyncio.Lock
    last_used: float


gemini_client: Optional[GeminiClient] = None
active_sessions: OrderedDict[Tuple[str, str], SessionEntry] = OrderedDict()
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


async def _init_client_unlocked() -> GeminiClient:
    """
    Inisialisasi GeminiClient secara atomik pada variabel lokal terlebih dahulu.
    Global `gemini_client` hanya di-assign setelah seluruh proses init & registrasi
    model selesai 100%, sehingga kegagalan tidak meninggalkan objek rusak.
    """
    global gemini_client
    cookies = load_cookies()
    psid = cookies.get("__Secure-1PSID")
    psidts = cookies.get("__Secure-1PSIDTS")

    if not psid:
        raise RuntimeError(
            "Cookies not found in cookies.json or GEMINI_SECURE_1PSID env var!"
        )

    print("[Bridge] Menginisialisasi GeminiClient via HTTP RPC...", flush=True)
    client = GeminiClient(
        secure_1psid=psid,
        secure_1psidts=psidts,
        auto_refresh=True
    )
    await client.init()

    registry = getattr(client, "_model_registry", None)
    if isinstance(registry, dict):
        # Registrasi & Pemetaan Model 4 Neon (Deeper analysis - Model# 3)
        try:
            neon_model = client.resolve_model("neon")
            if neon_model:
                registry["gemini-neon"] = neon_model
                registry["gemini-4-neon"] = neon_model
                registry["neon"] = neon_model
                # Backward-compatibility alias: argon -> neon
                registry["gemini-4-argon"] = neon_model
                registry["argon"] = neon_model
        except Exception as e:
            print(f"[Bridge Warning] Model Neon tidak ditemukan di RPC registry: {e}", flush=True)

        # Registrasi & Pemetaan Model 4 Carbon (Code & complex work - Model# 8)
        try:
            carbon_model = client.resolve_model("carbon")
            if carbon_model:
                registry["gemini-carbon"] = carbon_model
                registry["gemini-4-carbon"] = carbon_model
                registry["carbon"] = carbon_model
        except Exception as e:
            print(f"[Bridge Warning] Model Carbon tidak ditemukan di RPC registry: {e}", flush=True)

        # Registrasi & Pemetaan Model 4 Hydrogen (Everyday help - Model# 1)
        try:
            hydrogen_model = client.resolve_model("hydrogen")
            if hydrogen_model:
                registry["gemini-4-hydrogen"] = hydrogen_model
                registry["gemini-hydrogen"] = hydrogen_model
                registry["hydrogen"] = hydrogen_model
        except Exception as e:
            print(f"[Bridge Warning] Model Hydrogen tidak ditemukan di RPC registry: {e}", flush=True)

        # Registrasi & Pemetaan Model Auto (Adapts to your needs - Model# 6)
        try:
            auto_model = client.resolve_model("auto")
            if auto_model:
                registry["gemini-auto"] = auto_model
                registry["auto"] = auto_model
        except Exception as e:
            print(f"[Bridge Warning] Model Auto tidak ditemukan di RPC registry: {e}", flush=True)

        # Bersihkan sisa alias lama yang sudah tidak valid
        registry.pop("gemini-pro", None)
        registry.pop("pro", None)

    # Atomic commit ke global hanya setelah semua tahap sukses
    gemini_client = client
    print(
        "[Bridge] Terhubung sukses ke Google Gemini! "
        "(100% Bebas Browser | 4 Neon Aktif Model# 3 | 4 Carbon Aktif Model# 8 | "
        "4 Hydrogen Aktif Model# 1 | Auto Aktif Model# 6)",
        flush=True
    )
    return client


async def init_client() -> GeminiClient:
    async with init_lock:
        if gemini_client is not None:
            return gemini_client
        return await _init_client_unlocked()


async def ensure_client() -> GeminiClient:
    if gemini_client is not None:
        return gemini_client
    async with init_lock:
        if gemini_client is None:
            await _init_client_unlocked()
    if gemini_client is None:
        raise RuntimeError(
            "Gagal menginisialisasi GeminiClient. Periksa cookies.json atau environment variables."
        )
    return gemini_client


def resolve_target_model(model_name: Optional[str], mode: str = "chat") -> Tuple[str, str]:
    raw = (model_name or "").lower().strip()

    # Auto-detect mode from model suffix e.g. "gemini-neon:task", "carbon:task", "argon:task"
    if ":task" in raw:
        mode = "task"
        raw = raw.replace(":task", "").strip()
    elif ":chat" in raw:
        mode = "chat"
        raw = raw.replace(":chat", "").strip()

    effective_mode = "task" if mode == "task" else "chat"
    target = raw

    carbon_keywords = ("carbon", "code", "coding", "complex")
    neon_keywords = ("neon", "argon", "deeper", "analysis", "analisis", "research", "audit")
    hydrogen_keywords = ("hydrogen", "everyday", "fast")
    auto_keywords = ("auto", "adapt", "flash", "lite", "quick")

    # MODE TASK (Resmi Google Project Remy: 4 Carbon, 4 Neon & 4 Hydrogen)
    if effective_mode == "task":
        if any(k in target for k in carbon_keywords):
            return "gemini-carbon", "task"
        if any(k in target for k in neon_keywords):
            return "gemini-neon", "task"
        if any(k in target for k in hydrogen_keywords):
            return "gemini-4-hydrogen", "task"
        return "gemini-neon", "task"

    # MODE CHAT: Carbon > Neon (alias Argon) > Hydrogen > Auto
    if any(k in target for k in carbon_keywords):
        return "gemini-carbon", "chat"
    if any(k in target for k in neon_keywords):
        return "gemini-neon", "chat"
    if any(k in target for k in hydrogen_keywords):
        return "gemini-4-hydrogen", "chat"
    if any(k in target for k in auto_keywords):
        return "gemini-auto", "chat"

    # Default umum: gemini-neon
    return "gemini-neon", "chat"


def extract_text_from_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts)
    return str(content) if content is not None else ""


def is_authorized(headers: Dict[str, str]) -> bool:
    """Validasi Bearer token menggunakan perbandingan constant-time jika BRIDGE_API_KEY aktif."""
    if not BRIDGE_API_KEY:
        return True
    auth_header = headers.get("authorization", "").strip()
    if not auth_header.lower().startswith("bearer "):
        return False
    token = auth_header[7:].strip()
    return hmac.compare_digest(token, BRIDGE_API_KEY)


async def get_or_create_session(
    mode: str,
    session_id: str,
    target_model: str
) -> SessionEntry:
    client = await ensure_client()
    session_key = (mode, session_id)
    now = time.time()

    async with session_lock:
        if session_key in active_sessions:
            active_sessions.move_to_end(session_key)
            entry = active_sessions[session_key]
            entry.last_used = now
            return entry

        if len(active_sessions) >= MAX_SESSIONS:
            evicted_key, _ = active_sessions.popitem(last=False)
            print(f"[Bridge] Menggusur sesi tidak aktif (LRU): mode={evicted_key[0]}", flush=True)

        # Jika session_id adalah Google CID asli (c_...), lampirkan langsung ke thread tersebut
        cid_param = session_id if session_id.startswith("c_") else ""
        chat = client.start_chat(model=target_model, cid=cid_param)
        entry = SessionEntry(chat=chat, lock=asyncio.Lock(), last_used=now)
        active_sessions[session_key] = entry
        return entry


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
    session_label = "Stateful" if session_id else "Single-turn"
    print(
        f"[Bridge] Mode: {effective_mode.upper()} | Model: '{target_model}' "
        f"(Session: {session_label}, Thinking: {actual_thinking}, RemyTask: {is_task})...",
        flush=True
    )

    if session_id:
        entry = await get_or_create_session(effective_mode, session_id, target_model)
        async with entry.lock:
            if target_model and entry.chat.model != target_model:
                entry.chat.model = target_model
            entry.last_used = time.time()
            response = await entry.chat.send_message(
                prompt,
                extended_thinking=actual_thinking,
                task_mode=is_task
            )
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
    session_label = "Stateful" if session_id else "Single-turn"
    print(
        f"[Bridge] Mode: {effective_mode.upper()} (Stream) | Model: '{target_model}' "
        f"(Session: {session_label}, Thinking: {actual_thinking}, RemyTask: {is_task})...",
        flush=True
    )

    if session_id:
        entry = await get_or_create_session(effective_mode, session_id, target_model)
        async with entry.lock:
            if target_model and entry.chat.model != target_model:
                entry.chat.model = target_model
            entry.last_used = time.time()
            async for chunk in entry.chat.send_message_stream(
                prompt,
                extended_thinking=actual_thinking,
                task_mode=is_task
            ):
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
        if not writer.is_closing():
            writer.close()
        await writer.wait_closed()
    except Exception:
        pass


async def send_json_response(
    writer: asyncio.StreamWriter,
    status_code: int,
    status_text: str,
    data: dict,
    indent: bool = False,
    extra_headers: str = ""
):
    res_bytes = json_dumps(data, indent=indent)
    response = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: application/json; charset=utf-8\r\n"
        f"Content-Length: {len(res_bytes)}\r\n"
        f"Connection: close\r\n"
        f"{CORS_HEADERS}"
        f"{extra_headers}"
        f"\r\n"
    ).encode("utf-8") + res_bytes
    writer.write(response)
    await writer.drain()


async def send_sse_error_and_done(writer: asyncio.StreamWriter, message: str):
    """Kirim frame error SSE JSON yang valid diikuti [DONE] jika header 200 OK sudah terkirim."""
    try:
        err_event = {
            "error": {
                "message": message,
                "type": "bridge_stream_error"
            }
        }
        writer.write(b"data: " + json_dumps(err_event) + b"\n\n")
        writer.write(b"data: [DONE]\n\n")
        await writer.drain()
    except Exception:
        pass


async def http_handler(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    headers_sent = False
    try:
        # P1: Anti-Slowloris total header timeout & batas jumlah baris header
        header_lines = []
        deadline = time.monotonic() + HEADER_TOTAL_TIMEOUT
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                await send_json_response(writer, 408, "Request Timeout", {
                    "error": {"message": "Header read timeout exceeded", "type": "request_timeout"}
                })
                await close_writer(writer)
                return

            try:
                line = await asyncio.wait_for(reader.readline(), timeout=remaining)
            except asyncio.TimeoutError:
                await send_json_response(writer, 408, "Request Timeout", {
                    "error": {"message": "Header read timeout exceeded", "type": "request_timeout"}
                })
                await close_writer(writer)
                return

            if not line or line in (b"\r\n", b"\n"):
                break

            header_lines.append(line.decode("utf-8", errors="replace").rstrip("\r\n"))
            if len(header_lines) > MAX_HEADERS + 1:  # +1 untuk request line
                await send_json_response(writer, 431, "Request Header Fields Too Large", {
                    "error": {
                        "message": f"Header count exceeds limit ({MAX_HEADERS})",
                        "type": "invalid_request_error"
                    }
                })
                await close_writer(writer)
                return

        if not header_lines:
            await close_writer(writer)
            return

        request_line = header_lines[0].strip().split()
        if len(request_line) < 2:
            await send_json_response(writer, 400, "Bad Request", {
                "error": {"message": "Malformed HTTP request line", "type": "invalid_request_error"}
            })
            await close_writer(writer)
            return

        method, raw_path = request_line[0].upper(), request_line[1]
        clean_path = raw_path.split("?")[0].rstrip("/")
        if not clean_path:
            clean_path = "/"

        # Parse headers ke dictionary case-insensitive + validasi Content-Length
        headers_map: Dict[str, str] = {}
        content_length: Optional[int] = None
        for h in header_lines[1:]:
            if ":" not in h:
                continue
            key, val = h.split(":", 1)
            key_lower = key.strip().lower()
            val_stripped = val.strip()
            if key_lower == "content-length":
                try:
                    parsed_len = int(val_stripped)
                except ValueError:
                    await send_json_response(writer, 400, "Bad Request", {
                        "error": {"message": "Invalid Content-Length header", "type": "invalid_request_error"}
                    })
                    await close_writer(writer)
                    return
                if parsed_len < 0:
                    await send_json_response(writer, 400, "Bad Request", {
                        "error": {"message": "Content-Length cannot be negative", "type": "invalid_request_error"}
                    })
                    await close_writer(writer)
                    return
                if content_length is not None and content_length != parsed_len:
                    await send_json_response(writer, 400, "Bad Request", {
                        "error": {"message": "Conflicting Content-Length headers", "type": "invalid_request_error"}
                    })
                    await close_writer(writer)
                    return
                content_length = parsed_len
            headers_map[key_lower] = val_stripped

        if method == "OPTIONS":
            response = (
                "HTTP/1.1 204 No Content\r\n"
                "Connection: close\r\n"
                f"{CORS_HEADERS}\r\n"
            ).encode("utf-8")
            writer.write(response)
            await writer.drain()
            await close_writer(writer)
            return

        body_len = content_length or 0
        if body_len > MAX_BODY_BYTES:
            await send_json_response(writer, 413, "Payload Too Large", {
                "error": {"message": "Payload Terlalu Besar (Max 2MB)", "type": "payload_too_large"}
            })
            await close_writer(writer)
            return

        body = b""
        if body_len > 0:
            try:
                body = await asyncio.wait_for(reader.readexactly(body_len), timeout=READ_TIMEOUT)
            except asyncio.TimeoutError:
                await send_json_response(writer, 408, "Request Timeout", {
                    "error": {"message": "Body read timeout exceeded", "type": "request_timeout"}
                })
                await close_writer(writer)
                return
            except asyncio.IncompleteReadError:
                await send_json_response(writer, 400, "Bad Request", {
                    "error": {"message": "Incomplete request body", "type": "invalid_request_error"}
                })
                await close_writer(writer)
                return

        # Health endpoint (disanitasi: tanpa membocorkan Google CID atau raw session ID)
        if clean_path in ("/health", "/") and method == "GET":
            chat_count = sum(1 for (m, _) in active_sessions if m == "chat")
            task_count = sum(1 for (m, _) in active_sessions if m == "task")
            status_obj = {
                "status": "online",
                "mode": "Direct HTTP RPC (Metode 2 - Tanpa Browser)",
                "client_initialized": gemini_client is not None,
                "auth_enabled": bool(BRIDGE_API_KEY),
                "gemini_ui_modes": ["chat", "task"],
                "task_models": [
                    "Code & complex work (4 Carbon - Model# 8)",
                    "Deeper analysis (4 Neon - Model# 3)",
                    "Everyday help (4 Hydrogen - Model# 1)"
                ],
                "active_sessions_count": len(active_sessions),
                "active_sessions_by_mode": {
                    "chat": chat_count,
                    "task": task_count
                },
                "capabilities": {
                    "task_mode": "Agentic task execution (4 Carbon, 4 Neon & 4 Hydrogen) without manual thinking toggle",
                    "chat_mode": "Full conversational models with optional thinking toggles",
                    "session_isolation": True,
                    "per_session_locking": True,
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

        # Autentikasi opsional Bearer token untuk seluruh endpoint /v1/*
        if clean_path.startswith("/v1/") and not is_authorized(headers_map):
            await send_json_response(
                writer,
                401,
                "Unauthorized",
                {
                    "error": {
                        "message": "Invalid or missing Bearer token",
                        "type": "authentication_error"
                    }
                },
                extra_headers="WWW-Authenticate: Bearer\r\n"
            )
            await close_writer(writer)
            return

        if clean_path == "/v1/models" and method == "GET":
            models_obj = {
                "object": "list",
                "data": [
                    {
                        "id": "gemini-carbon",
                        "object": "model",
                        "owned_by": "google-deepmind",
                        "description": "Code & complex work (4 Carbon - Model# 8)",
                        "modes": ["chat", "task"]
                    },
                    {
                        "id": "gemini-neon",
                        "object": "model",
                        "owned_by": "google-deepmind",
                        "description": "Deeper analysis (4 Neon - Model# 3)",
                        "modes": ["chat", "task"]
                    },
                    {
                        "id": "gemini-4-neon",
                        "object": "model",
                        "owned_by": "google-deepmind",
                        "description": "Deeper analysis (4 Neon - Model# 3)",
                        "modes": ["chat", "task"]
                    },
                    {
                        "id": "gemini-4-argon",
                        "object": "model",
                        "owned_by": "google-deepmind",
                        "description": "Backward-compatibility alias for 4 Neon",
                        "modes": ["chat", "task"]
                    },
                    {
                        "id": "gemini-4-hydrogen",
                        "object": "model",
                        "owned_by": "google-deepmind",
                        "description": "Everyday help (4 Hydrogen - Model# 1)",
                        "modes": ["chat", "task"]
                    },
                    {
                        "id": "gemini-auto",
                        "object": "model",
                        "owned_by": "google-deepmind",
                        "description": "Adapts to your needs (Auto - Model# 6)",
                        "modes": ["chat"]
                    }
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

                if not isinstance(req_json, dict):
                    await send_json_response(writer, 400, "Bad Request", {
                        "error": {"message": "Request body must be a JSON object", "type": "invalid_request_error"}
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
                if mode not in ("task", "chat"):
                    mode = "chat"

                resolved_model, effective_mode = resolve_target_model(model, mode=mode)
                session_id = req_json.get("session_id") or req_json.get("conversation_id")
                is_stateless = bool(req_json.get("stateless", False))
                is_stream = bool(req_json.get("stream", False))

                # AUTO-SESSION & STICKY CONTINUATION:
                # Default bridge adalah STATEFUL / BERSAMBUNG (bukan stateless terpecah-pecah)
                if not session_id and not is_stateless:
                    if len(messages) > 1:
                        seed_parts = [
                            f"{m.get('role')}:{extract_text_from_content(m.get('content', '')).strip()}"
                            for m in messages
                            if isinstance(m, dict) and m.get("role") in ("system", "user")
                        ][:2]
                        if seed_parts:
                            raw_seed = "|".join(seed_parts).encode("utf-8")
                            session_id = f"auto-{hashlib.sha256(raw_seed).hexdigest()[:16]}"
                    else:
                        session_id = f"sticky-{effective_mode}-session"

                # Check thinking level
                thinking_level = req_json.get("thinking_level") or req_json.get("reasoning_effort")
                extended_thinking = (
                    bool(req_json.get("extended_thinking", False)) or
                    str(thinking_level).lower() in ("high", "extended", "tinggi", "true", "1")
                )

                # Ekstraksi prompt:
                # Cek keberadaan sesi dengan namespace (effective_mode, session_id)
                session_key = (effective_mode, session_id) if session_id else None
                session_exists = bool(session_key and session_key in active_sessions)

                if session_exists:
                    last_msg = messages[-1] if isinstance(messages[-1], dict) else {}
                    prompt = extract_text_from_content(last_msg.get("content", ""))
                elif len(messages) == 1:
                    first_msg = messages[0] if isinstance(messages[0], dict) else {}
                    prompt = extract_text_from_content(first_msg.get("content", ""))
                else:
                    parts = []
                    for m in messages:
                        if not isinstance(m, dict):
                            continue
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
                    # Pastikan client siap sebelum mengirim header HTTP 200 OK
                    await ensure_client()

                    sse_headers = (
                        "HTTP/1.1 200 OK\r\n"
                        "Content-Type: text/event-stream; charset=utf-8\r\n"
                        "Cache-Control: no-cache\r\n"
                        "Connection: close\r\n"
                        f"{CORS_HEADERS}\r\n"
                    ).encode("utf-8")
                    writer.write(sse_headers)
                    await writer.drain()
                    headers_sent = True

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

                entry = active_sessions.get(session_key) if session_key else None
                conv_id = getattr(entry.chat, "cid", None) if entry else None

                openai_resp = {
                    "id": completion_id,
                    "object": "chat.completion",
                    "created": created_ts,
                    "model": resolved_model,
                    "mode": effective_mode,
                    "session_id": session_id,
                    "conversation_id": conv_id,
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

            except (ConnectionResetError, BrokenPipeError):
                await close_writer(writer)
                return
            except Exception as e:
                if headers_sent:
                    # P0: Safe SSE Error Framing — jangan kirim HTTP/1.1 500 mentah setelah 200 OK
                    await send_sse_error_and_done(writer, str(e))
                else:
                    err_body = {
                        "error": {
                            "message": str(e),
                            "type": "bridge_error"
                        }
                    }
                    await send_json_response(writer, 500, "Internal Server Error", err_body)
                await close_writer(writer)
                return

        await send_json_response(writer, 404, "Not Found", {
            "error": {"message": "Not Found", "type": "not_found"}
        })
        await close_writer(writer)

    except (ConnectionResetError, BrokenPipeError):
        await close_writer(writer)
    except Exception as e:
        print(f"[HTTP Error] {e}", flush=True)
        if headers_sent:
            await send_sse_error_and_done(writer, str(e))
        await close_writer(writer)


async def main():
    print("=" * 60, flush=True)
    print("  🚀 GEMINI DIRECT RPC BRIDGE (Metode 2 - 100% Tanpa Browser)", flush=True)
    print("=" * 60, flush=True)
    print(f"[*] OpenAI API Server: http://{HTTP_HOST}:{HTTP_PORT}/v1", flush=True)
    print(f"[*] Health Check     : http://{HTTP_HOST}:{HTTP_PORT}/health", flush=True)
    print(f"[*] Bearer Auth      : {'ENABLED' if BRIDGE_API_KEY else 'DISABLED (localhost only)'}", flush=True)
    print("=" * 60, flush=True)

    server = await asyncio.start_server(http_handler, HTTP_HOST, HTTP_PORT)
    print(f"[*] Socket listening on http://{HTTP_HOST}:{HTTP_PORT}. Inisialisasi Google client...", flush=True)

    try:
        await init_client()
    except Exception as e:
        print(f"[Bridge Warning] Inisialisasi awal client gagal (akan di-retry otomatis): {e}", flush=True)

    await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Bridge] Server dimatikan.")
