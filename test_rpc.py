import asyncio
import json
import os
import sys
from gemini_webapi import GeminiClient

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "cookies.json")


def load_cookies() -> dict:
    data = {}
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"[Warning] Could not parse {COOKIE_FILE}: {e}", flush=True)
    if not data.get("__Secure-1PSID"):
        env_psid = os.environ.get("GEMINI_SECURE_1PSID")
        env_psidts = os.environ.get("GEMINI_SECURE_1PSIDTS")
        if env_psid:
            data["__Secure-1PSID"] = env_psid
            if env_psidts:
                data["__Secure-1PSIDTS"] = env_psidts
    return data


async def main():
    cookies = load_cookies()
    psid = cookies.get("__Secure-1PSID")
    psidts = cookies.get("__Secure-1PSIDTS")

    if not psid:
        print("[ERROR] Please provide valid cookies in cookies.json or set GEMINI_SECURE_1PSID env var.", flush=True)
        sys.exit(1)

    print("[1] Menginisialisasi GeminiClient via HTTP RPC...", flush=True)
    client = GeminiClient(
        secure_1psid=psid,
        secure_1psidts=psidts
    )

    try:
        await client.init()
        print("[2] Terhubung sukses! SNlM0e nonce didapatkan.", flush=True)

        prompt = "Berapa 12 x 12? Jawab hanya dengan angka hasilnya saja!"
        print(f"[3] Mengirimkan prompt: '{prompt}'...", flush=True)

        response = await client.generate_content(prompt)
        print("\n" + "=" * 50)
        print("HASIL JAWABAN LANGSUNG DARI GOOGLE GEMINI:")
        print("=" * 50)
        print(response.text)
        print("=" * 50)

        await client.close()
    except Exception as e:
        print(f"[ERROR]: {e}", flush=True)
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
