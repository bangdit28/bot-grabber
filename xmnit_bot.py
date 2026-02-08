import cloudscraper # Ganti requests jadi cloudscraper
import time, os

# AMBIL DATA DARI KOYEB
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

# Bikin scraper sakti (Bypass Cloudflare)
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'mobile': False,
    }
)

def kirim_tele(pesan):
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        scraper.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan})
    except: pass

def tembak_get_number(range_num):
    api_url = f"https://x.mnitnetwork.com/mdashboard/getnum?range={range_num}"
    
    headers = {
        'Cookie': MNIT_COOKIE,
        'mauthtoken': MNIT_TOKEN,
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://x.mnitnetwork.com/mauth/dashboard',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    try:
        # Gunakan scraper.get bukan requests.get
        res = scraper.get(api_url, headers=headers, timeout=20)
        print(f"DEBUG MNIT: {res.status_code} - Respon: {res.text[:100]}")
        
        if res.status_code == 200:
            if len(res.text) < 25:
                return res.text.strip()
            try:
                data = res.json()
                return data.get('number') or data.get('data', {}).get('number')
            except:
                return None
        elif res.status_code == 403:
            # Jika masih 403, berarti Cloudflare benar-benar ketat
            return "403_ERROR"
        return None
    except Exception as e:
        print(f"⚠️ Error Bypass: {e}")
        return None

def run_xmnit():
    print("LOG: X-MNIT Anti-Cloudflare Started...")
    while True:
        try:
            req = scraper.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if req:
                for req_id, val in req.items():
                    target = val.get('range')
                    if target:
                        print(f"🚀 Memproses Get Number: {target}")
                        nomor = tembak_get_number(target)
                        
                        if nomor and nomor != "403_ERROR":
                            scraper.post(f"{FIREBASE_URL}/active_numbers.json", json={
                                "number": nomor,
                                "range": target,
                                "timestamp": int(time.time())
                            })
                            kirim_tele(f"✅ X-MNIT: Nomor Didapat!\n{nomor}")
                        elif nomor == "403_ERROR":
                            kirim_tele("⚠️ Cloudflare Memblokir! Ambil COOKIE baru dari F12.")
                    
                    scraper.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(1.5)
        except: time.sleep(5)
