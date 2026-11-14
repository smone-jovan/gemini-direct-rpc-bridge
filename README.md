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
- **The Complete 2×2 Execution Matrix**: Full architectural support for **Stateless Chat**, **Stateful Chat**, **Stateless Task**, and **Stateful Task**.
- **LRU Cache Eviction**: Managed with `collections.OrderedDict` bounded up to 100 concurrent sessions, preventing unbounded memory growth.
- **Production-Grade Concurrency Protection**: Built-in `asyncio.Lock` with double-checked locking prevents cold-start race conditions and duplicate authentication storms.
- **Automated Keepalive**: Background session auto-refresh keeps cookies alive continuously.
- **Flexible Credential Loading**: Supports `cookies.json` or environment variables (`GEMINI_SECURE_1PSID`, `GEMINI_SECURE_1PSIDTS`).

---

### 🧩 The 2×2 Architecture Matrix: Chat vs. Task & Stateless vs. Stateful

In the official Google Gemini interface and agentic engineering, **Execution Mode (`mode`)** and **Memory State (`session_id`)** are two orthogonal dimensions. They combine into four distinct operational modes:

| Dimension | **Chat Mode** (`"mode": "chat"`) | **Task Mode** (`"mode": "task"`) |
| :--- | :--- | :--- |
| **Stateless**<br>*(Explicit `"stateless": true`)* | **1. Stateless Chat**<br>One-off conversational inquiry without history or memory retention. Ideal for quick translations, definitions, and one-liner queries. | **3. Stateless Task**<br>Single-turn autonomous agent execution without history pollution. Runs directly on **4 Argon** (Code & analysis) or **4 Hydrogen** (Everyday help). |
| **Stateful**<br>*(Default / `session_id` / Auto)* | **2. Stateful Chat**<br>Multi-turn conversational dialogue where conversational context and memory are preserved across turns in the same Google thread. | **4. Stateful Task**<br>Multi-turn agentic task where past instructions, decisions, and task state are maintained across consecutive steps with `<ElicitationsGroup>` action cards. |

> 📖 **Deep Dive Specification**: Read [ARCHITECTURE.md](ARCHITECTURE.md) for full empirical reverse-engineering data, HAR capture traces, and protobuf wire specifications.

#### 🔄 Multi-Turn Continuity & Sticky Sessions
- **Default Stateful**: Sequential requests now automatically continue in the **same Google conversation thread** (`sticky-task-session` or `sticky-chat-session`), completely eliminating fragmented 1-message orphan threads in your browser sidebar.
- **Auto-Session Derivation**: For clients that do not pass a `session_id` (e.g. Cursor, Continue.dev), the bridge automatically derives a persistent session ID using SHA-256 over the initial user prompt.
- **Direct Google Thread Attachment**: Pass `"conversation_id": "c_..."` to append turns directly to any existing Google conversation thread from your browser history!

---

### 🔍 Google Gemini UI Alignment: Chat vs. Task (Project Remy)

In Google Gemini's official UI, there is a dedicated toggle pill: **`[ Chat | Task ]`**:

1. **Mode `Chat`**:
   - Conversational assistant mode (`featureMode: 0`).
   - Access to full model spectrum (`gemini-carbon`, `gemini-4-argon`, `gemini-4-hydrogen`, `gemini-flash-lite`). Legacy 3.1 Pro has been purged.
   - Supports manual **Thinking Level** adjustments (`thinking_level: "high"` / `"low"`).
2. **Mode `Task`** (*Activates `+ Describe task` / "Tag me in! What's next?"*):
   - Autonomous agentic pipeline powered by Google's **Project Remy** (`featureMode: 40`).
   - Strictly restricted by Google to **exactly two engines**:
     - **`Everyday help`** $\rightarrow$ **4 Hydrogen** (`model_number: 1`)
     - **`Code & analysis`** $\rightarrow$ **4 Argon** (`model_number: 8`, identifier `"argon"`)
   - **No Manual Thinking Toggle**: Google omits the manual thinking slider in Task mode because planning and reasoning are handled autonomously by the backend agent loop.

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

#### 5. Run the Bridge
```bash
python bridge.py
```
Or double-click `Jalankan_Bridge.bat` (Windows).

The local endpoint will be online at `http://127.0.0.1:8765/v1`.

---

### 💡 Usage Examples for All 4 Modes

#### 1. Mode 1: Stateless Chat (cURL)
```bash
curl -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "chat",
    "model": "gemini-4-hydrogen",
    "messages": [
      {"role": "user", "content": "What is the boiling point of water in Kelvin?"}
    ]
  }'
```

#### 2. Mode 2: Stateful Chat (Multi-Turn with `session_id`)
```bash
# Turn 1
curl -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "chat",
    "session_id": "session-dev-chat",
    "messages": [{"role": "user", "content": "My secret key is 8842."}]
  }'

# Turn 2 (Context remembered!)
curl -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "chat",
    "session_id": "session-dev-chat",
    "messages": [{"role": "user", "content": "What was my secret key?"}]
  }'
```

#### 3. Mode 3: Stateless Task (Code & Analysis with 4 Argon)
You can specify mode via `"mode": "task"` or directly in the model name suffix `"model": "gemini-4-argon:task"`:
```bash
# Using model suffix (IDE / Cursor friendly)
curl -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-4-argon:task",
    "messages": [
      {"role": "user", "content": "Analyze dual-pivot quicksort worst-case complexity and provide a C99 implementation."}
    ]
  }'

# Or using explicit mode parameter
curl -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "task",
    "model": "gemini-4-hydrogen",
    "messages": [
      {"role": "user", "content": "Summarize the key requirements for PCI-DSS compliance."}
    ]
  }'
```

#### 4. Mode 4: Stateful Task (Multi-Turn Pipeline with Memory Retention)
```bash
# Step 1
curl -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "task",
    "model": "gemini-4-hydrogen",
    "session_id": "task-pipeline-1",
    "messages": [{"role": "user", "content": "Define the JSON schema for a payment webhook."}]
  }'

# Step 2 (Prior decisions and schemas are retained!)
curl -X POST http://127.0.0.1:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "task",
    "model": "gemini-4-hydrogen",
    "session_id": "task-pipeline-1",
    "messages": [{"role": "user", "content": "Write unit tests covering that exact schema."}]
  }'
```

#### 5. Integration with Cursor / Continue.dev
In your `config.json` for Continue or Cursor AI:
```json
{
  "models": [
    {
      "title": "Gemini 4 Hydrogen (Local Bridge)",
      "provider": "openai",
      "model": "gemini-4-hydrogen",
      "apiBase": "http://127.0.0.1:8765/v1",
      "apiKey": "local"
    },
    {
      "title": "Gemini 4 Argon (Local Bridge)",
      "provider": "openai",
      "model": "gemini-4-argon",
      "apiBase": "http://127.0.0.1:8765/v1",
      "apiKey": "local"
    }
  ]
}
```

---

## 🇮🇩 Dokumentasi Bahasa Indonesia

### 🌟 Gambaran Umum & Fitur Unggulan

**Gemini Direct RPC Bridge** adalah jembatan HTTP RPC lokal berkinerja tinggi yang memungkinkan Anda mengakses model Google Gemini Web secara gratis dengan protokol OpenAI-compatible tanpa membuka jendela peramban (browser) sama sekali.

- **100% Tanpa Browser**: Beroperasi sepenuhnya di latar belakang via HTTP RPC native (`curl-cffi` + `gemini-webapi`). Tidak membutuhkan Chrome, Selenium, atau ekstensi.
- **Konsumsi Memori Sangat Hemat (~25 MB RAM)**: Berjalan stabil tanpa membebani sistem Anda.
- **Mendukung Matriks Eksekusi 2×2 Lengkap**:
  - **Stateless Chat** vs **Stateful Chat**
  - **Stateless Task** vs **Stateful Task**
- **Dukungan Streaming Real-Time (SSE)**: Mendukung parameter `"stream": true` secara native via Server-Sent Events untuk Cursor, Continue.dev, dan AI IDE modern.
- **Akselerasi Serialisasi orjson**: Kecepatan pemrosesan JSON ultra-cepat dengan fallback otomatis ke library standar `json`.
- **Manajemen Memori Bounded LRU**: Menggusur sesi terlama secara otomatis bila melampaui 100 sesi aktif (*anti memory leak*).
- **Proteksi Concurrency Cold-Start**: Dilengkapi `asyncio.Lock` agar terhindar dari *race condition* autentikasi saat request masuk serempak.

---

### 🧩 Matriks Arsitektur 2×2: Chat vs Task & Stateless vs Stateful

Dalam antarmuka resmi Google Gemini dan rekayasa AI modern, **Mode Eksekusi (`mode`)** dan **Status Memori (`session_id`)** adalah dua dimensi yang terpisah:

| Dimensi | **Mode Chat** (`"mode": "chat"`) | **Mode Task** (`"mode": "task"`) |
| :--- | :--- | :--- |
| **Stateless**<br>*(Eksplisit `"stateless": true`)* | **1. Stateless Chat**<br>Tanya-jawab satu kali tanpa riwayat percakapan. Cocok untuk terjemahan cepat, definisi, atau tanya rumus instan. | **3. Stateless Task**<br>Eksekusi tugas agen otonom satu kali tanpa mencemari riwayat obrolan. Berjalan langsung di **4 Argon** (Code & analysis) atau **4 Hydrogen** (Everyday help). |
| **Stateful**<br>*(Default / `session_id` / Auto)* | **2. Stateful Chat**<br>Percakapan multi-turn bersambung di mana konteks dan memori percakapan diingat lintas giliran obrolan di thread yang sama. | **4. Stateful Task**<br>Tugas otonom bertahap di thread Task yang sama, memori keputusan terjaga, lengkap dengan action cards `<ElicitationsGroup>`. |

> 📖 **Dokumentasi Mendalam Arsitektur**: Baca [ARCHITECTURE.md](ARCHITECTURE.md) untuk data bedah biner lengkap dari berkas tangkapan HAR (189.9 MB), struktur protobuf WebChannel, dan pemetaan flag Project Remy.

#### 🔄 Multi-Turn Bersambung & Sesi Sticky Default
- **Default Stateful**: Permintaan berurutan kini otomatis bersambung di **thread Google yang SAMA** (`sticky-task-session` atau `sticky-chat-session`), menghapus masalah tumpukan chat 1-pesan yang terpotong-potong di sidebar browser Anda.
- **Auto-Session Derivation**: Untuk klien yang tidak mengirimkan `session_id` (seperti Cursor atau Continue.dev), bridge secara otomatis membuat ID sesi persisten dari seed SHA-256 pesan pembuka.
- **Sambung Langsung ke Thread Web**: Sertakan `"conversation_id": "c_..."` untuk langsung meneruskan giliran obrolan ke thread yang sudah ada di sidebar web Google Gemini Anda!

---

### 🔍 Penyelarasan Antarmuka Resmi Gemini: Chat vs. Task (Project Remy)

Di antarmuka resmi Google Gemini, terdapat tombol fisik pemilih: **`[ Chat | Task ]`**:

1. **Mode `Chat`**:
   - Mode percakapan umum (`featureMode: 0`).
   - Pilihan model mutakhir sesuai hierarki: **Carbon > Argon > Hydrogen > Flash-Lite** (`gemini-carbon`, `gemini-4-argon`, `gemini-4-hydrogen`, `gemini-flash-lite`). Model lama 3.1 Pro telah dihapus total.
   - Menyediakan setelan manual **Thinking Level** (`thinking_level: "high"` / `"low"`).
2. **Mode `Task`** (*Mengaktifkan input `+ Describe task` / "Tag me in! What's next?"*):
   - Pipeline agen otonom khusus yang ditenagai oleh **Project Remy** (`featureMode: 40`).
   - Dibatasi secara ketat oleh Google hanya pada **dua mesin penggerak**:
     - **`Everyday help`** $\rightarrow$ **4 Hydrogen** (`model_number: 1`)
     - **`Code & analysis`** $\rightarrow$ **4 Argon** (`model_number: 8`, identifier string `"argon"`)
   - **Tanpa Toggle Thinking Manual**: Google meniadakan slider thinking manual di mode Task karena proses penalaran dan perencanaan agen sudah berjalan otomatis di arsitektur internal Google.

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
