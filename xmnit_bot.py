from curl_cffi import requests
import time, os, json

# DATA DARI KOYEB
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
MY_UA = os.getenv("MY_UA")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

def kirim_tele(pesan):
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        import requests as req_tele
        req_tele.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan}, timeout=5)
    except: pass

def tembak_get_number(range_num):
    api_url = f"https://x.mnitnetwork.com/mdashboard/getnum?range={range_num}"
    
    headers = {
        'authority': 'x.mnitnetwork.com',
        'accept': 'application/json, text/plain, */*',
        'cookie': MNIT_COOKIE,
        'mauthtoken': MNIT_TOKEN,
        'referer': 'https://x.mnitnetwork.com/mauth/dashboard',
        'user-agent': MY_UA,
        'x-requested-with': 'XMLHttpRequest',
    }
    
    try:
        # Tembak pake impersonate chrome
        res = requests.get(api_url, headers=headers, impersonate="chrome", timeout=30)
        
        # --- DEBUG AREA ---
        print(f"--- RESPON DARI MNIT (Status: {res.status_code}) ---")
        print(res.text) # KITA LIAT ISI ASLINYA DI LOG KOYEB
        print("------------------------------------------")
        
        if res.status_code == 200:
            if "Just a moment" in res.text:
                return "CF_BLOCKED"
            
            # 1. Cek jika responnya JSON
            try:
                data = res.json()
                return data.get('number') or data.get('data', {}).get('number')
            except:
                # 2. Jika responnya teks mentah, kita coba cari angka nomor di dalemnya
                # Kita ambil 5-15 digit angka dari respon
                import re
                numbers = re.findall(r'\d{10,15}', res.text)
                if numbers:
                    return numbers[0] # Ambil angka pertama yang ketemu
                
                # 3. Jika isinya mauthtoken panjang, berarti nomornya masuk ke list 'Active'
                if "mauthtoken" in res.text:
                    return "CHECK_ACTIVE_LIST"
        return None
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None

def run_xmnit():
    print("🚀 X-MNIT Stealth Mode Started...")
    kirim_tele("🚀 Bot X-MNIT Stealth Aktif! Cloudflare Tembus!")
    
    while True:
        try:
            import requests as req_fire
            res_fire = req_fire.get(f"{FIREBASE_URL}/perintah_bot.json")
            req = res_fire.json()
            
            if req:
                for req_id, val in req.items():
                    target = val.get('range')
                    if target:
                        print(f"🚀 Proses Range: {target}")
                        nomor = tembak_get_number(target)
                        
                        if nomor == "CF_BLOCKED":
                            kirim_tele("⚠️ Cloudflare mendeteksi Bot! Ambil Cookie baru.")
                        elif nomor == "CHECK_ACTIVE_LIST":
                            kirim_tele("✅ Perintah Berhasil, Nomor Sedang Dialokasikan. Cek Dashboard!")
                        elif nomor:
                            # BERHASIL DAPET NOMOR LANGSUNG
                            req_fire.post(f"{FIREBASE_URL}/active_numbers.json", json={
                                "number": nomor,
                                "range": target,
                                "timestamp": int(time.time())
                            })
                            kirim_tele(f"✅ X-MNIT: Nomor Didapat!\n{nomor}")
                        else:
                            print("❌ Gagal urai nomor dari respon.")
                    
                    req_fire.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(2)
        except Exception as e:
            time.sleep(5)
