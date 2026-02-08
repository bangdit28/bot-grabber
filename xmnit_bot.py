import requests, time, os

# AMBIL DATA DARI KOYEB
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN") # Variabel baru
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

s = requests.Session()

def tembak_get_number(range_num):
    api_url = f"https://x.mnitnetwork.com/mdashboard/getnum?range={range_num}"
    
    # Kuncinya di sini: Kita kirim Cookie DAN mauthtoken secara terpisah
    headers = {
        'Cookie': MNIT_COOKIE,
        'mauthtoken': MNIT_TOKEN, # Ini header rahasianya
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://x.mnitnetwork.com/mauth/dashboard',
        'X-Requested-With': 'XMLHttpRequest'
    }
    
    try:
        res = s.get(api_url, headers=headers, timeout=15)
        print(f"DEBUG MNIT: {res.status_code} - Respon: {res.text[:100]}")
        
        if res.status_code == 200:
            # Karena responnya teks panjang (mauthtoken), bot harus pinter
            # Kita coba ambil teksnya, kalau itu nomor (pendek) kita balikin
            if len(res.text) < 25:
                return res.text.strip()
            # Kalau responnya JSON, ambil field number
            try:
                data = res.json()
                return data.get('number') or data.get('data', {}).get('number')
            except:
                return None
        elif res.status_code == 403:
            return "403_ERROR"
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

# ... sisanya sama kayak sebelumnya ...

def run_xmnit():
    print("LOG: X-MNIT Worker Started (GET Method)...")
    while True:
        try:
            req = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if req:
                for req_id, val in req.items():
                    target = val.get('range')
                    if not target: continue
                    
                    print(f"🚀 Memproses Get Number: {target}")
                    nomor_baru = tembak_get_number(target)
                    
                    if nomor_baru:
                        requests.post(f"{FIREBASE_URL}/active_numbers.json", json={
                            "number": nomor_baru,
                            "range": target,
                            "timestamp": int(time.time())
                        })
                        kirim_tele(f"✅ X-MNIT: Nomor Didapat!\n{nomor_baru}")
                    
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(1.5)
        except Exception as e:
            time.sleep(5)
