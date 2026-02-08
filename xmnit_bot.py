from curl_cffi import requests
import time, os, threading

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
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        req_tele.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan}, timeout=5)
    except: pass

# --- FUNGSI GRAB SMS DARI X-MNIT (CONSOLES) ---
def grab_sms_mnit():
    print("LOG: SMS Grabber X-MNIT Started...")
    # URL API Console tempat lo liat nomor & kode OTP
    api_console_url = "https://x.mnitnetwork.com/mapi/v1/mdashboard/console"
    
    headers = {
        'cookie': MNIT_COOKIE,
        'mauthtoken': MNIT_TOKEN,
        'user-agent': MY_UA,
        'accept': 'application/json, text/plain, */*',
        'x-requested-with': 'XMLHttpRequest'
    }
    
    done_ids = []
    
    while True:
        try:
            # Pake curl_cffi biar tembus Cloudflare pas cek SMS
            res = requests.get(api_console_url, headers=headers, impersonate="chrome", timeout=30)
            
            if res.status_code == 200:
                data = res.json()
                # MNIT biasanya naruh list nomor & kode di data['data']
                items = data.get('data', [])
                
                for item in items:
                    # Ambil nomor lo (copy), kode OTP (code), dan status
                    num = item.get('copy') 
                    code = item.get('code')
                    status = item.get('status') # 'success' kalo kode udah ada
                    
                    if code and num:
                        # Gabungin pesan biar rapi di web
                        full_msg = f"<#> {code} is your Facebook code"
                        uid = f"{num}_{code}" # Biar gak spam/dobel masuk Firebase
                        
                        if uid not in done_ids:
                            import requests as req_fire
                            # POST ke /messages biar muncul di accordion web lo
                            req_fire.post(f"{FIREBASE_URL}/messages.json", json={
                                "liveSms": num, # Harus sama dengan nomor di active_numbers
                                "messageContent": full_msg,
                                "timestamp": int(time.time() * 1000)
                            })
                            done_ids.append(uid)
                            print(f"📩 OTP Masuk: {num} -> {code}")
                            kirim_tele(f"📩 OTP FB DIDAPAT!\nNomor: {num}\nKode: {code}")
            
            time.sleep(3) # Cek tiap 3 detik biar kenceng
        except Exception as e:
            print(f"Error Grab SMS: {e}")
            time.sleep(10)

# --- FUNGSI GET NUMBER (YG SUDAH BERHASIL) ---
def tembak_get_number(range_num):
    api_url = "https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number"
    headers = {'content-type': 'application/json','cookie': MNIT_COOKIE,'mauthtoken': MNIT_TOKEN,'user-agent': MY_UA}
    try:
        res = requests.post(api_url, headers=headers, json={"range": range_num}, impersonate="chrome", timeout=30)
        if res.status_code == 200:
            data = res.json()
            return data.get('data', {}).get('copy')
        return None
    except: return None

def run_xmnit():
    print("🚀 X-MNIT Stealth Engine Active...")
    # Jalankan SMS Grabber di background
    threading.Thread(target=grab_sms_mnit, daemon=True).start()
    
    while True:
        try:
            import requests as req_fire
            res = req_fire.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if res:
                for req_id, val in res.items():
                    target = val.get('range')
                    nomor = tembak_get_number(target)
                    if nomor:
                        req_fire.post(f"{FIREBASE_URL}/active_numbers.json", json={
                            "number": nomor,
                            "timestamp": int(time.time())
                        })
                    req_fire.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(2)
        except: time.sleep(5)
