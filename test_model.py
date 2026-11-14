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

    print("[1] Menghubungkan ke Google Gemini via Direct RPC (Metode 2)...", flush=True)
    client = GeminiClient(
        secure_1psid=psid,
        secure_1psidts=psidts
    )
    await client.init()

    prompt = "Halo Gemini 4 Hydrogen! Tolong sebutkan 3 hukum termodinamika secara sangat singkat dan padat!"
    print("[2] Mengirimkan pertanyaan ke model 'gemini-4-hydrogen'...", flush=True)

    # Generate content with model='gemini-4-hydrogen'
    response = await client.generate_content(prompt, model="gemini-4-hydrogen")

    print("\n" + "=" * 55)
    print("HASIL JAWABAN DARI GEMINI 4 HYDROGEN (MURNI HTTP RPC):")
    print("=" * 55)
    print(response.text)
    print("=" * 55)

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
