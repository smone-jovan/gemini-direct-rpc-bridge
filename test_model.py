import asyncio
import json
import os
import sys
from gemini_webapi import GeminiClient

COOKIE_FILE = os.path.join(os.path.dirname(__file__), "cookies.json")

def load_cookies():
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

async def main():
    cookies = load_cookies()
    psid = cookies.get("__Secure-1PSID")
    psidts = cookies.get("__Secure-1PSIDTS")
    
    if not psid:
        print("[ERROR] Please provide valid cookies in cookies.json", flush=True)
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
