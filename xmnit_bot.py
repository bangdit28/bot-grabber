from curl_cffi import requests as curl_req
import requests as normal_req
import time, os, threading, json

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
        normal_req.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan}, timeout=10)
    except Exception as e:
        print(f"Gagal kirim Tele: {e}")

# --- FUNGSI REQUEST NOMOR (GET NUMBER) ---
def tembak_get_number(range_num):
    api_url = "https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number"
    headers = {
        'content-type': 'application/json',
        'cookie': MNIT_COOKIE,
        'mauthtoken': MNIT_TOKEN,
        'user-agent': MY_UA,
        'x-requested-with': 'XMLHttpRequest'
    }
    try:
        res = curl_req.post(api_url, headers=headers, json={"range": range_num}, impersonate="chrome", timeout=30)
        if res.status_code == 200:
            data = res.json()
            # Ambil nomor dari data['data']['copy']
            return data.get('data', {}).get('copy')
        return None
    except: return None

# --- FUNGSI GRAB SMS (DARI TABEL INFO) ---
def grab_sms_mnit():
    print("LOG: SMS Grabber X-MNIT Aktif...")
    # URL API buat narik data tabel (Info)
    date_now = time.strftime("%Y-%m-%d")
    api_info = f"https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?date={date_now}&page=1&search=&status="
    
    headers = {
        'cookie': MNIT_COOKIE,
        'mauthtoken': MNIT_TOKEN,
        'user-agent': MY_UA,
        'accept': 'application/json'
    }
    
    done_ids = []
    
    while True:
        try:
            res = curl_req.get(api_info, headers=headers, impersonate="chrome", timeout=30)
            if res.status_code == 200:
                data = res.json()
                # Lo liat di logs nanti, MNIT naruh data di 'data' atau 'items'
                items = data.get('data', {}).get('data', [])
                
                for item in items:
                    num = item.get('copy') # Nomor lo
                    code = item.get('code') # Kode OTP (Warna ijo di web)
                    
                    if code and num:
                        msg = f"<#> {code} is your Facebook code"
                        uid = f"{num}_{code}"
                        
                        if uid not in done_ids:
                            # 1. Kirim ke Firebase Web lo
                            normal_req.post(f"{FIREBASE_URL}/messages.json", json={
                                "liveSms": num,
                                "messageContent": msg,
                                "timestamp": int(time.time() * 1000)
                            })
                            # 2. Kirim Notif Tele
                            kirim_tele(f"📩 OTP MNIT MASUK!\nNomor: {num}\nKode: {code}")
                            done_ids.append(uid)
                            print(f"✅ SMS Grabbed: {num} -> {code}")
            time.sleep(3)
        except: time.sleep(5)

# --- FUNGSI UTAMA (LISTENER PERINTAH) ---
def run_xmnit():
    print("🚀 X-MNIT STEALTH ENGINE STARTED...")
    kirim_tele("🚀 Bot X-MNIT Aktif 24 Jam! PC Boleh Mati.")
    
    # Jalankan SMS Grabber di background thread
    threading.Thread(target=grab_sms_mnit, daemon=True).start()
    
    while True:
        try:
            # Pantau perintah dari Firebase
            res_fire = normal_req.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if res_fire:
                for req_id, val in res_fire.items():
                    target = val.get('range')
                    print(f"🚀 Memproses Get Number: {target}")
                    
                    nomor = tembak_get_number(target)
                    
                    if nomor:
                        # 1. Masukin ke Firebase Biar Muncul di Web lo
                        normal_req.post(f"{FIREBASE_URL}/active_numbers.json", json={
                            "number": nomor,
                            "timestamp": int(time.time())
                        })
                        # 2. Notif Tele (WAJIB ADA)
                        kirim_tele(f"✅ X-MNIT: Nomor Didapat!\nNomor: {nomor}\nRange: {target}")
                        print(f"✅ Berhasil Get: {nomor}")
                    else:
                        kirim_tele(f"❌ X-MNIT: Gagal dapet nomor untuk {target}")

                    # Hapus perintah biar gak dobel
                    normal_req.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            
            time.sleep(1.5)
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(5)
