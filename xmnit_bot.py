import cloudscraper
import time, os

# DATA DARI KOYEB
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
MY_UA = os.getenv("MY_UA") # User-Agent asli dari browser lo
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

# Gunakan cloudscraper dengan settingan paling aman
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

def kirim_tele(pesan):
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        scraper.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan}, timeout=5)
    except: pass

def tembak_get_number(range_num):
    api_url = f"https://x.mnitnetwork.com/mdashboard/getnum?range={range_num}"
    
    # HEADERS HARUS LENGKAP DAN SAMA DENGAN CHROME
    headers = {
        'Cookie': MNIT_COOKIE,
        'mauthtoken': MNIT_TOKEN,
        'User-Agent': MY_UA, # WAJIB SAMA DENGAN CHROME PAS AMBIL COOKIE
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
        'Referer': 'https://x.mnitnetwork.com/mauth/dashboard',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    try:
        res = scraper.get(api_url, headers=headers, timeout=20)
        
        # JIKA MASIH KENA CLOUDFLARE (HTML)
        if "<!DOCTYPE html>" in res.text or "Just a moment" in res.text:
            print("❌ CLOUDFLARE MASIH MENGHALANGI")
            return "CF_BLOCKED"

        if res.status_code == 200:
            print(f"✅ RESPON MNIT: {res.text[:30]}")
            # Jika respon langsung nomor (teks pendek)
            if 5 < len(res.text) < 25:
                return res.text.strip()
            # Jika respon JSON
            try:
                data = res.json()
                return data.get('number') or data.get('data', {}).get('number')
            except:
                return None
        return None
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None

def run_xmnit():
    print("🚀 X-MNIT Listener Standby...")
    kirim_tele("🚀 X-MNIT Listener Standby!")
    
    while True:
        try:
            # Ambil perintah dari Firebase
            req = scraper.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if req:
                for req_id, val in req.items():
                    target = val.get('range')
                    if target:
                        nomor = tembak_get_number(target)
                        
                        if nomor == "CF_BLOCKED":
                            kirim_tele("⚠️ X-MNIT Gagal! Cloudflare minta 'tiket' baru. Ambil COOKIE + USER-AGENT dari Chrome sekarang.")
                        elif nomor:
                            # BERHASIL DAPET NOMOR
                            scraper.post(f"{FIREBASE_URL}/active_numbers.json", json={
                                "number": nomor,
                                "range": target,
                                "timestamp": int(time.time())
                            })
                            kirim_tele(f"✅ X-MNIT: Nomor Didapat!\nNomor: {nomor}")
                        else:
                            kirim_tele("❌ X-MNIT Gagal! Respon kosong (mungkin saldo abis).")
                    
                    # Hapus perintah biar gak dobel
                    scraper.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(1.5)
        except: time.sleep(5)
