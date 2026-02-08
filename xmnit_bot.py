from curl_cffi import requests
import time, os, re

FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
MY_UA = os.getenv("MY_UA")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

def kirim_tele(pesan):
    try:
        import requests as req_tele
        req_tele.post(f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage", 
                      data={'chat_id': TELE_CHAT_ID, 'text': pesan}, timeout=5)
    except: pass

def tembak_get_number(range_num):
    # --- URL API ASLI BERDASARKAN SS NETWORK TAB ---
    api_url = f"https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum?range={range_num}"
    
    headers = {
        'authority': 'x.mnitnetwork.com',
        'accept': 'application/json, text/plain, */*',
        'cookie': MNIT_COOKIE,
        'mauthtoken': MNIT_TOKEN,
        'referer': 'https://x.mnitnetwork.com/mdashboard/getnum',
        'user-agent': MY_UA,
        'x-requested-with': 'XMLHttpRequest',
    }
    
    try:
        # Tembak pake curl_cffi impersonate chrome
        res = requests.get(api_url, headers=headers, impersonate="chrome", timeout=30)
        
        print(f"DEBUG MNIT: {res.status_code}")
        
        # Jika respon masih HTML (Cloudflare ketat)
        if "<!DOCTYPE html>" in res.text:
            print("⚠️ Masih dapet HTML. Coba cek apakah Cookie cf_clearance sudah dimasukkan.")
            return "HTML_RESPONSE"

        if res.status_code == 200:
            raw_text = res.text.strip()
            print(f"ISI RESPON: {raw_text[:50]}") # Liat 50 karakter pertama
            
            # 1. Jika isinya angka doang
            if raw_text.isdigit() and 5 < len(raw_text) < 20:
                return raw_text
            
            # 2. Jika isinya JSON
            try:
                data = res.json()
                # Sesuaikan field 'number' dengan hasil Preview di Network Tab
                return data.get('number') or data.get('data', {}).get('number')
            except:
                # 3. Cari angka nomor di dalem teks pake Regex
                match = re.search(r'\d{10,15}', raw_text)
                return match.group(0) if match else None
        return None
    except Exception as e:
        print(f"Error API: {e}")
        return None

def run_xmnit():
    print("🚀 X-MNIT API Mode Started (mapi/v1)...")
    kirim_tele("🚀 Bot X-MNIT API Aktif! Jalur mapi/v1 digunakan.")
    
    while True:
        try:
            import requests as req_fire
            res_fire = req_fire.get(f"{FIREBASE_URL}/perintah_bot.json")
            req = res_fire.json()
            
            if req:
                for req_id, val in req.items():
                    target = val.get('range')
                    if target:
                        print(f"🚀 Memproses: {target}")
                        nomor = tembak_get_number(target)
                        
                        if nomor == "HTML_RESPONSE":
                            kirim_tele("⚠️ X-MNIT: Gagal! Masih dapet HTML. Update Cookie cf_clearance dari F12.")
                        elif nomor:
                            # Masukkan ke list nomor aktif agar muncul di dashboard lo
                            req_fire.post(f"{FIREBASE_URL}/active_numbers.json", json={
                                "number": nomor,
                                "range": target,
                                "timestamp": int(time.time()),
                                "status": "active"
                            })
                            kirim_tele(f"✅ X-MNIT: Nomor Didapat!\n{nomor}")
                        else:
                            print("❌ Gagal mendapatkan nomor.")
                    
                    # Hapus perintah agar tidak diproses berulang
                    req_fire.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(1.5)
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(5)
