import requests, time, os

# AMBIL DATA DARI KOYEB ENVIRONMENT
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

s = requests.Session()

def kirim_tele(pesan):
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan})
    except: pass

def tembak_get_number(range_num):
    # URL SESUAI TEMUAN LO (Metode GET)
    api_url = f"https://x.mnitnetwork.com/mdashboard/getnum?range={range_num}"
    
    headers = {
        'Cookie': MNIT_COOKIE,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Referer': 'https://x.mnitnetwork.com/mauth/dashboard'
    }
    
    try:
        # Pake GET sesuai URL yang lo kasih
        res = s.get(api_url, headers=headers, timeout=15)
        print(f"DEBUG MNIT: {res.status_code} - {res.text[:50]}...")
        
        if res.status_code == 200:
            # Karena di layar lo muncul teks panjang, kita coba ambil nomornya
            # Jika responnya JSON
            try:
                data = res.json()
                return data.get('number') or data.get('data', {}).get('number')
            except:
                # Jika responnya teks mentah, kita ambil teksnya (asumsi itu nomor)
                # Tapi kalau teksnya mauthtoken, berarti ada yang salah sama respon servernya
                if len(res.text) < 20: # Biasanya nomor telpon nggak panjang banget
                    return res.text.strip()
                return None
        elif res.status_code == 403:
            kirim_tele("⚠️ COOKIE X-MNIT DIBLOKIR/EXPIRED!")
            return None
        return None
    except Exception as e:
        print(f"⚠️ Error Get Number: {e}")
        return None

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
