# Gemini Direct RPC Bridge 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://www.python.org/)
[![Memory Footprint](https://img.shields.io/badge/RAM-~25MB-success.svg)](#architecture-comparison)
[![API Standard](https://img.shields.io/badge/API-OpenAI%20Compatible-orange.svg)](#usage-examples)

Headless, high-performance, ultra-low memory (~25 MB RAM) Direct HTTP RPC Bridge for Google Gemini Web. Exposes an OpenAI-compatible `/v1/chat/completions` API endpoint with multi-session isolation, double-checked concurrency locking, LRU cache eviction, and extended reasoning toggles.

> **Read this in:** [English](#english-documentation) | [Bahasa Indonesia](#-dokumentasi-bahasa-indonesia)

---

## English Documentation

### 🌟 Key Features

- **100% Browserless & Headless**: Direct HTTP RPC via `gemini-webapi` and `curl-cffi`. No Chrome, Puppeteer, Selenium, or Xvfb needed.
- **Ultra-Low Memory Footprint**: Runs at **~25 MB of RAM** idle/active (compared to 600 MB–1.5 GB for browser automation).
- **OpenAI Compatible**: Seamless drop-in replacement exposing `/v1/chat/completions`, `/v1/models`, and `/health`. Works out-of-the-box with Cursor, Continue, Cline, and OpenAI SDKs.
- **Real-Time SSE Streaming**: Native Server-Sent Events (`stream: true`) support delivers low-latency chunked streaming directly to modern AI coding assistants.
- **High-Performance JSON Engine**: Accelerated by `orjson` with automatic fallback to standard library `json`.
- **Multi-Session Isolation**:
  - **Task Mode (Stateless)**: One-off prompts execute without polluting conversational history.
  - **Chat Mode (Stateful)**: Multi-turn conversations track context deterministically when `session_id` is passed.
- **LRU Cache Eviction**: Managed with `collections.OrderedDict` bounded up to 100 concurrent sessions, preventing unbounded memory growth.
- **Production-Grade Concurrency Protection**: Built-in `asyncio.Lock` with double-checked locking prevents cold-start race conditions and duplicate authentication storms.
- **Extended Thinking & Model Mapping**:
  - `gemini-4-hydrogen` / `fast`: Super-fast everyday tasks.
  - `gemini-pro` / `argon` / `research`: Deep reasoning mode with `thinking_level: high`.
  - `gemini-carbon`: Extreme-frontier reasoning (Most complex work, available for eligible Google One AI Premium/Ultra accounts).
  - `gemini-flash-lite`: Low-latency quick answers.
- **Automated Keepalive**: Background session auto-refresh keeps cookies alive continuously.
- **Flexible Credential Loading**: Supports `cookies.json` or environment variables (`GEMINI_SECURE_1PSID`, `GEMINI_SECURE_1PSIDTS`).

---

### 🏗️ Architecture Comparison

| Metric / Feature | Browser Extension Bridge | Headless Selenium / Puppeteer | **Gemini Direct RPC Bridge** |
| :--- | :--- | :--- | :--- |
| **RAM Footprint** | ~150 MB – 350 MB | 600 MB – 1.5 GB | **~25 MB** |
| **GUI / Browser Required** | Yes (Chrome must stay open) | Yes (Headless browser process) | **No (Pure HTTP socket server)** |
| **Background Service** | Fragile (tab unload risk) | Heavy CPU / memory drain | **Lightweight native asyncio loop** |
| **Response Latency** | High (DOM injection delays) | High (DOM rendering overhead) | **Low (Direct protobuf / RPC wire speed)** |
| **DOM Drift Resilience** | Breaks when UI updates | Breaks when UI updates | **Resilient (Direct internal RPC endpoint)** |
| **Session Isolation** | Shared single browser tab | Cumbersome multi-profile tabs | **Native LRU session map via `session_id`** |

---

### 🚀 Quick Start Guide

#### 1. Requirements
- Python 3.10 or higher
- A Google account logged into [Google Gemini](https://gemini.google.com)

#### 2. Obtain Your Session Cookies
1. Open your browser and navigate to [https://gemini.google.com](https://gemini.google.com).
2. Ensure you are logged in.
3. Open Developer Tools (`F12` or `Ctrl + Shift + I` / `Cmd + Option + I`).
4. Go to the **Application** tab (or **Storage** in Firefox) -> **Cookies** -> `https://gemini.google.com`.
5. Find and copy the values of:
   - `__Secure-1PSID`
   - `__Secure-1PSIDTS`

#### 3. Configuration
Clone the repository and copy the template:
```bash
git clone https://github.com/smone-jovan/gemini-direct-rpc-bridge.git
cd gemini-direct-rpc-bridge
cp cookies.json.example cookies.json
```

Edit `cookies.json` with your credentials:
```json
{
  "__Secure-1PSID": "your_cookie_value_here",
  "__Secure-1PSIDTS": "your_cookie_value_here"
}
```

*Alternatively, you can provide environment variables instead of creating `cookies.json`:*
```bash
export GEMINI_SECURE_1PSID="your_cookie_value_here"
export GEMINI_SECURE_1PSIDTS="your_cookie_value_here"
```

#### 4. Installation
```bash
pip install -r requirements.txt
```

#### 5. Launch the Server
```bash
python bridge.py
```
Or on Windows, double-click `Jalankan_Bridge.bat` (or use `start_bridge_silent.vbs` to run silently in the background).

The server will be available at:
- **Base URL**: `http://127.0.0.1:8765/v1`
- **Health Check**: `http://127.0.0.1:8765/health`

---

### 💻 Usage Examples

#### 1. cURL (Stateless Prompt)
```bash
curl -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-4-hydrogen",
    "messages": [
      {"role": "user", "content": "Explain quantum entanglement in 2 sentences."}
    ]
  }'
```

#### 2. cURL (Deep Reasoning with Argon)
```bash
curl -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-pro",
    "thinking_level": "high",
    "messages": [
      {"role": "user", "content": "Analyze the time complexity of dual-pivot quicksort in edge cases."}
    ]
  }'
```

#### 3. cURL (Stateful Multi-Turn Conversation)
```bash
# Turn 1
curl -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-workspace-1",
    "messages": [{"role": "user", "content": "My secret code is 4299."}]
  }'

# Turn 2 (Context remembered!)
curl -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "session-workspace-1",
    "messages": [{"role": "user", "content": "What was my secret code?"}]
  }'
```

#### 4. Python OpenAI Client
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8765/v1",
    api_key="not-needed"
)

response = client.chat.completions.create(
    model="gemini-4-hydrogen",
    messages=[
        {"role": "system", "content": "You are an expert engineer."},
        {"role": "user", "content": "Write a fast Fibonacci generator in Python."}
    ]
)

print(response.choices[0].message.content)
```

#### 5. Integration with Cursor / Continue.dev
In your `config.json` for Continue or Cursor AI:
```json
{
  "models": [
    {
      "title": "Gemini Hydrogen (Local Bridge)",
      "provider": "openai",
      "model": "gemini-4-hydrogen",
      "apiBase": "http://127.0.0.1:8765/v1",
      "apiKey": "local"
    },
    {
      "title": "Gemini Argon Reasoning (Local Bridge)",
      "provider": "openai",
      "model": "gemini-pro",
      "apiBase": "http://127.0.0.1:8765/v1",
      "apiKey": "local"
    }
  ]
}
```

---

## 🇮🇩 Dokumentasi Bahasa Indonesia

### 🌟 Gambaran Umum & Fitur Unggulan

**Gemini Direct RPC Bridge** adalah jembatan HTTP RPC lokal yang memungkinkan Anda mengakses kecerdasan Google Gemini Web secara gratis dengan protokol OpenAI-compatible tanpa membuka jendela peramban (browser) sama sekali.

- **100% Tanpa Browser**: Beroperasi sepenuhnya di latar belakang via HTTP RPC native (`curl-cffi` + `gemini-webapi`). Tidak membutuhkan Chrome, Selenium, atau ekstensi.
- **Konsumsi Memori Sangat Hemat (~25 MB RAM)**: Berjalan stabil tanpa membebani sistem Anda.
- **Pemisahan Mode Chat vs Task**:
  - **Task Mode**: Panggilan mandiri (*stateless*) untuk eksekusi perintah tanpa menyimpan riwayat.
  - **Chat Mode**: Obrolan multi-turn dengan konteks berkelanjutan menggunakan `session_id`.
- **Dukungan Streaming Real-Time (SSE)**: Mendukung parameter `"stream": true` secara native via Server-Sent Events untuk Cursor, Continue.dev, dan AI IDE modern.
- **Akselerasi Serialisasi orjson**: Kecepatan pemrosesan JSON ultra-cepat dengan fallback otomatis ke library standar `json`.
- **Manajemen Memori Bounded LRU**: Menggusur sesi terlama secara otomatis bila melampaui 100 sesi aktif (*anti memory leak*).
- **Proteksi Concurrency Cold-Start**: Dilengkapi `asyncio.Lock` agar terhindar dari *race condition* autentikasi saat request masuk serempak.
- **Dukungan Model**:
  - `gemini-4-hydrogen`: Kecepatan tinggi untuk eksekusi tugas harian.
  - `gemini-pro` (Argon): Penalaran mendalam (*deep reasoning*) dengan dukungan `thinking_level: high`.
  - `gemini-carbon`: Penalaran ekstrem tingkat lanjut (*Most complex work*, aktif jika akun Google Anda memiliki akses Google One AI Premium/Ultra).
  - `gemini-flash-lite`: Respons cepat dan ringkas.

---

### 🚀 Panduan Memulai Cepat

#### 1. Persiapan
Pastikan Python 3.10+ telah terpasang.

#### 2. Mengambil Cookie Sesi Google
1. Buka [https://gemini.google.com](https://gemini.google.com) di browser Anda dan pastikan sudah login.
2. Buka DevTools (`F12`).
3. Masuk ke tab **Application** (atau **Storage** di Firefox) -> **Cookies** -> `https://gemini.google.com`.
4. Salin nilai dari dua cookie:
   - `__Secure-1PSID`
   - `__Secure-1PSIDTS`

#### 3. Konfigurasi
Salin file template `cookies.json.example` menjadi `cookies.json`:
```bash
cp cookies.json.example cookies.json
```
Isi nilai cookie yang sudah disalin ke dalam `cookies.json`.

*(Opsional: Anda juga bisa menyetel environment variable `GEMINI_SECURE_1PSID` dan `GEMINI_SECURE_1PSIDTS`).*

#### 4. Instalasi Dependensi
```bash
pip install -r requirements.txt
```

#### 5. Menjalankan Server
```bash
python bridge.py
```
Atau klik ganda `Jalankan_Bridge.bat` (Windows).

Endpoint lokal akan aktif di `http://127.0.0.1:8765/v1`.

---

## 🔒 Security & Privacy Notice

- File `cookies.json` Anda berisi kredensial autentikasi sesi Google pribadi. **JANGAN PERNAH** membagikan atau mengunggah file `cookies.json` ke repositori publik.
- File `.gitignore` pada proyek ini telah dikonfigurasi secara ketat untuk memblokir `cookies.json`, `.env`, serta file log lokal.

---

## 📜 License

Didistribusikan di bawah lisensi MIT. Lihat berkas [LICENSE](LICENSE) untuk informasi lebih lanjut.

Copyright (c) 2026 smone-jovan
