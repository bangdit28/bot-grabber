import requests, time, os

# AMBIL DATA DARI KOYEB ENVIRONMENT
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE") # Kita balik pake Cookie manual
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

s = requests.Session()

def kirim_tele(pesan):
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan})
    except: pass

def tembak_get_number(range_num):
    # Pastikan URL ini sesuai dengan hasil F12 lo
    api_url = "https://x.mnitnetwork.com/api/v1/mdashboard/get" 
    
    headers = {
        'Cookie': MNIT_COOKIE,
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://x.mnitnetwork.com/dashboard',
        'Origin': 'https://x.mnitnetwork.com',
        'Accept': 'application/json'
    }
    
    payload = {"range": range_num}
    
    try:
        res = s.post(api_url, json=payload, headers=headers, timeout=15)
        print(f"DEBUG MNIT: {res.status_code} - {res.text}")
        
        if res.status_code == 200:
            data = res.json()
            num = data.get('number') or data.get('data', {}).get('number')
            return num
        elif res.status_code == 403:
            kirim_tele("⚠️ COOKIE X-MNIT DIBLOKIR/EXPIRED! Silakan ganti Cookie di Koyeb.")
            return None
        return None
    except Exception as e:
        print(f"⚠️ Error Get Number: {e}")
        return None

def run_xmnit():
    print("LOG: X-MNIT Listener Started (Manual Cookie Mode)...")
    
    while True:
        try:
            # Pantau perintah dari Firebase
            req = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            
            if req:
                for req_id, val in req.items():
                    target = val.get('range')
                    if not target: continue
                    
                    print(f"🚀 Memproses Get Number: {target}")
                    nomor_baru = tembak_get_number(target)
                    
                    if nomor_baru:
                        # Masukkan ke list Active Numbers lo di Firebase
                        requests.post(f"{FIREBASE_URL}/active_numbers.json", json={
                            "number": nomor_baru,
                            "range": target,
                            "timestamp": int(time.time())
                        })
                        kirim_tele(f"✅ X-MNIT: Nomor Didapat!\nNomor: {nomor_baru}")
                    else:
                        print(f"❌ Gagal ambil nomor untuk {target}")
                    
                    # Hapus perintah biar gak dobel
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            
            time.sleep(1.5)
        except Exception as e:
            print(f"Error Loop: {e}")
            time.sleep(5)
