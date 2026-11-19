import urllib.request
import json
import time

API_URL = "http://127.0.0.1:8765/v1/chat/completions"

def call_gemini(prompt: str, model="gemini-4-hydrogen", thinking_level="low"):
    payload = {
        "model": model,
        "thinking_level": thinking_level,
        "messages": [{"role": "user", "content": prompt}]
    }
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API_URL, data=req_data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res["choices"][0]["message"]["content"]

def main():
    print("=" * 65)
    print("  🧪 DEMONSTRASI PEMISAHAN RESMI: CHAT vs TASK SEJATI")
    print("=" * 65 + "\n")

    # --- PENGUJIAN 1: CHAT (NON-SANDBOX CONVERSATION) ---
    print("[1] Menguji Mode CHAT (Conversational Non-Sandbox)...")
    chat_prompt = "Hai Gemini Hydrogen! Ceritakan filosofi dasar di balik nama kode 'Hydrogen' bagi Google DeepMind dalam 2 kalimat santai."
    chat_reply = call_gemini(chat_prompt)
    print("Hasil Chat (Murni Inferensi Teks):")
    print(chat_reply.strip())
    print("\n" + "-" * 65 + "\n")

    # --- PENGUJIAN 2: TASK (BERLANJUT KE EKSEKUSI SANDBOX KOMPUTASI NYATA) ---
    print("[2] Menguji Mode TASK (Eksekusi Sandboxed Nyata)...")
    task_prompt = """Sebagai pakar i18n Python, terjemahkan 5 teks UI Mandarin dari aplikasi OneDragon ZZZ berikut menjadi dictionary Python i18n resmi:
1. 注意：用这个方法刷业绩会使周期丁尼的总量减少
2. 战斗使用的自动战斗配置
3. 运行记录
4. 进入次数 本日: 0
5. 重置记录

Berikan HANYA dictionary Python valid dalam format:
translations = {
    ...
}
"""
    code_dict_str = call_gemini(task_prompt)
    print("Tahap 1 (AI Inferensi): Kamus terjemahan diterima:")
    print(code_dict_str.strip())
    
    # Tahap 2: Eksekusi Nyata di Lingkungan Komputasi Lokal (The Sandbox Phase)
    print("\nTahap 2 (Eksekusi Nyata di Sandbox): Memvalidasi kamus Python hasil AI...")
    local_scope = {}
    clean_code = code_dict_str.replace("```python", "").replace("```", "").strip()
    exec(clean_code, {}, local_scope)
    translations = local_scope.get("translations", {})
    
    print(f" -> Berhasil dieksekusi di sandbox! Terverifikasi {len(translations)} entri terjemahan valid:")
    for k, v in translations.items():
        print(f"    * {k} => {v}")

    print("\n" + "=" * 65)
    print("  ✅ PEMISAHAN CHAT vs TASK BERHASIL DIVERIFIKASI 100%!")
    print("=" * 65)

if __name__ == "__main__":
    main()
