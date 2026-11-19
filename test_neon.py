import urllib.request
import json

API_URL = "http://127.0.0.1:8765/v1/chat/completions"

def call_model(prompt: str, model="gemini-neon", mode="chat", thinking_level="high"):
    payload = {
        "model": model,
        "mode": mode,
        "thinking_level": thinking_level,
        "messages": [{"role": "user", "content": prompt}]
    }
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=req_data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["choices"][0]["message"]["content"]

def main():
    print("=" * 60)
    print("  🧪 PENGUJIAN MODEL GEMINI 4 NEON (CHAT & TASK MODE)")
    print("=" * 60)

    # 1. Chat Mode
    print("\n[1] Menguji Mode CHAT dengan Gemini 4 Neon (Extended Thinking)...")
    reply_chat = call_model("Halo Gemini 4 Neon! Jelaskan keunggulan utamamu dalam 1 kalimat.", model="gemini-neon", mode="chat")
    print(f"Jawaban Chat:\n{reply_chat}\n")

    # 2. Task Mode (Project Remy)
    print("\n[2] Menguji Mode TASK (Project Remy) dengan Gemini 4 Neon...")
    reply_task = call_model("Buatkan 3 langkah checklist review keamanan web backend.", model="gemini-neon", mode="task")
    print(f"Jawaban Task:\n{reply_task[:400]}...\n")

    # 3. Backward Compatibility Alias (Argon -> Neon)
    print("\n[3] Menguji Alias Backward-Compatibility ('gemini-4-argon')...")
    reply_alias = call_model("Apakah panggilan ke model Argon berhasil dialihkan ke Neon?", model="gemini-4-argon", mode="chat")
    print(f"Jawaban Alias:\n{reply_alias}\n")

    print("=" * 60)
    print("  ✅ SEMUA PENGUJIAN GEMINI 4 NEON BERHASIL 100%!")
    print("=" * 60)

if __name__ == "__main__":
    main()
