import cloudscraper
import time, os

# AMBIL DATA DARI KOYEB
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
)

def kirim_tele(pesan):
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        scraper.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan}, timeout=5)
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
        res = scraper.get(api_url, headers=headers, timeout=20)
        print(f"DEBUG MNIT: {res.status_code} - Respon: {res.text[:50]}")
        
        # CEK JIKA TERDETEKSI CLOUDFLARE (ISI HTML)
        if "<!DOCTYPE html>" in res.text or "<html" in res.text:
            return "CLOUDFLARE_BLOCKED"

        if res.status_code == 200:
            # Jika respon pendek (asumsi itu nomor)
            if 5 < len(res.text) < 25:
                return res.text.strip()
            # Jika respon JSON
            try:
                data = res.json()
                return data.get('number') or data.get('data', {}).get('number')
            except:
                return None
        elif res.status_code == 403:
            return "COOKIE_EXPIRED"
            
        return None
    except Exception as e:
        print(f"⚠️ Error Bypass: {e}")
        return None

def run_xmnit():
    # NOTIFIKASI SAAT BOT BARU NYALA (SESUAI REQUEST LO)
    print("LOG: X-MNIT Anti-Cloudflare Started...")
    kirim_tele("🚀 X-MNIT Listener Aktif & Standby!")
    
    while True:
        try:
            req = scraper.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if req:
                for req_id, val in req.items():
                    target = val.get('range')
                    if target:
                        print(f"🚀 Memproses Get Number: {target}")
                        nomor = tembak_get_number(target)
                        
                        if nomor == "CLOUDFLARE_BLOCKED":
                            kirim_tele(f"⚠️ X-MNIT: Gagal! Terdeteksi Cloudflare (Just a moment). Lo harus ambil COOKIE baru dari F12 Chrome.")
                        elif nomor == "COOKIE_EXPIRED":
                            kirim_tele(f"⚠️ X-MNIT: Cookie Expired/403. Ganti Cookie di Koyeb.")
                        elif nomor:
                            # BERHASIL DAPET NOMOR
                            requests.post(f"{FIREBASE_URL}/active_numbers.json", json={
                                "number": nomor,
                                "range": target,
                                "timestamp": int(time.time())
                            })
                            kirim_tele(f"✅ X-MNIT: Nomor Didapat!\nNomor: {nomor}")
                        else:
                            kirim_tele(f"❌ X-MNIT: Gagal dapet nomor. Respon kosong/saldo abis.")
                    
                    # Hapus perintah dari firebase
                    scraper.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(1.5)
        except Exception as e:
            print(f"Error Loop MNIT: {e}")
            time.sleep(5)
