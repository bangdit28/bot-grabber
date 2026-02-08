from curl_cffi import requests
import time, os, re

# DATA DARI KOYEB
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
    api_url = "https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number"
    headers = {
        'authority': 'x.mnitnetwork.com',
        'content-type': 'application/json',
        'cookie': MNIT_COOKIE,
        'mauthtoken': MNIT_TOKEN,
        'referer': 'https://x.mnitnetwork.com/mdashboard/getnum',
        'user-agent': MY_UA,
        'x-requested-with': 'XMLHttpRequest',
    }
    payload = {"range": range_num}
    
    try:
        res = requests.post(api_url, headers=headers, json=payload, impersonate="chrome", timeout=30)
        if res.status_code == 200:
            data = res.json()
            # AMBIL DARI data['data']['copy'] SESUAI LOG KOYEB LO
            return data.get('data', {}).get('copy')
        return None
    except:
        return None

def run_xmnit():
    print("🚀 X-MNIT API Engine Running...")
    
    while True:
        try:
            import requests as req_fire
            res_fire = req_fire.get(f"{FIREBASE_URL}/perintah_bot.json")
            req = res_fire.json()
            
            if req:
                for req_id, val in req.items():
                    target = val.get('range')
                    if target:
                        nomor = tembak_get_number(target)
                        
                        if nomor:
                            # --- BAGIAN PENTING: JALUR FIREBASE ---
                            # Jika di web belum muncul, coba ganti 'active_numbers' 
                            # jadi 'allocations' atau 'numbers'
                            path_tujuan = "active_numbers" 
                            
                            req_fire.post(f"{FIREBASE_URL}/{path_tujuan}.json", json={
                                "number": nomor,
                                "range": target,
                                "timestamp": int(time.time()),
                                "status": "active"
                            })
                            kirim_tele(f"✅ X-MNIT: Nomor Didapat!\n{nomor}")
                        else:
                            kirim_tele("❌ X-MNIT: Gagal dapet nomor. Cek saldo/cookie.")
                    
                    req_fire.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(1.5)
        except:
            time.sleep(5)
