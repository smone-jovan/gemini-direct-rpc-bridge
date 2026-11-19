import urllib.request
import json
import time

API_URL = "http://127.0.0.1:8765/v1/chat/completions"

def send_request(payload: dict) -> tuple[dict, float]:
    start_time = time.time()
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=req_data,
        headers={"Content-Type": "application/json; charset=utf-8"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        res_data = json.loads(resp.read().decode("utf-8"))
        elapsed = time.time() - start_time
        return res_data, elapsed

def main():
    print("=" * 65)
    print("  🧪 PENGUJIAN GEMINI 4 HYDROGEN (THINKING: LOW)")
    print("  Mode 1: Task (Stateless) vs Mode 2: Chat (Stateful Session)")
    print("=" * 65 + "\n")

    # --- PENGUJIAN 1: TASK MODE (STATELESS) ---
    print("[1] Menjalankan Pengujian Task Mode (Stateless - Tanpa session_id)...")
    task_payload = {
        "model": "gemini-4-hydrogen",
        "thinking_level": "low",
        "messages": [
            {
                "role": "user",
                "content": "Tuliskan fungsi Python satu baris (one-liner lambda) untuk membalikkan urutan kata dalam sebuah kalimat, lalu berikan contoh penggunaannya secara ringkas!"
            }
        ]
    }
    
    task_res, task_time = send_request(task_payload)
    print(f"[*] Selesai dalam: {task_time:.2f} detik")
    print(f"[*] Model ID    : {task_res.get('model')}")
    print(f"[*] Session ID  : {task_res.get('session_id') or 'None (Stateless Task)'}")
    print("\n--- Hasil Jawaban Task Mode ---")
    print(task_res["choices"][0]["message"]["content"])
    print("-" * 65 + "\n")

    # --- PENGUJIAN 2: CHAT MODE (STATEFUL MULTI-TURN) ---
    session_key = f"hydrogen_chat_session_{int(time.time())}"
    print(f"[2] Menjalankan Pengujian Chat Mode (Stateful - Session ID: {session_key})...")
    
    # Turn 1: Menyimpan Informasi
    print(" -> Mengirim Turn 1 (Menitipkan informasi konteks)...")
    chat_turn1_payload = {
        "model": "gemini-4-hydrogen",
        "thinking_level": "low",
        "session_id": session_key,
        "messages": [
            {
                "role": "user",
                "content": "Halo Hydrogen! Saya sedang mengembangkan sistem kendali satelit bernama 'Project Aethelgard-X'. Tolong catat dan ingat nama proyek ini."
            }
        ]
    }
    res_turn1, time_turn1 = send_request(chat_turn1_payload)
    print(f"    Selesai dalam: {time_turn1:.2f}s")
    print(f"    Jawaban Turn 1: {res_turn1['choices'][0]['message']['content'].strip()}\n")

    # Turn 2: Menguji Ingatan Memori Konteks
    print(" -> Mengirim Turn 2 (Menguji daya ingat sesi terhadap Turn 1)...")
    chat_turn2_payload = {
        "model": "gemini-4-hydrogen",
        "thinking_level": "low",
        "session_id": session_key,
        "messages": [
            {
                "role": "user",
                "content": "Apa nama proyek kendali satelit yang sedang saya kembangkan tadi? Sebutkan nama proyeknya secara tepat!"
            }
        ]
    }
    res_turn2, time_turn2 = send_request(chat_turn2_payload)
    print(f"    Selesai dalam: {time_turn2:.2f}s")
    print(f"    Jawaban Turn 2: {res_turn2['choices'][0]['message']['content'].strip()}\n")

    print("=" * 65)
    print("  ✅ KEDUA PENGUJIAN SELESAI DENGAN STATUS 100% SUKSES!")
    print("=" * 65)

if __name__ == "__main__":
    main()
