from curl_cffi import requests
import time, os, threading

# DATA KOYEB
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
MY_UA = os.getenv("MY_UA")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

# --- GRAB SMS DARI CONSOLE X-MNIT ---
def grab_sms_mnit():
    print("LOG: Grabber SMS X-MNIT Aktif...")
    url_console = "https://x.mnitnetwork.com/mapi/v1/mdashboard/console"
    headers = {'cookie': MNIT_COOKIE, 'mauthtoken': MNIT_TOKEN, 'user-agent': MY_UA}
    done_ids = []

    while True:
        try:
            # Pake curl_cffi buat tembus Cloudflare
            res = requests.get(url_console, headers=headers, impersonate="chrome", timeout=30)
            if res.status_code == 200:
                data = res.json()
                items = data.get('data', [])
                for item in items:
                    msg = item.get('message') or item.get('text')
                    num = item.get('phone') or item.get('number')
                    
                    if not msg or not num: continue
                    
                    # UID unik biar gak dobel kirim
                    uid = f"{num}_{msg[:10]}"
                    if uid not in done_ids:
                        # KIRIM KE FIREBASE (Path: /messages)
                        import requests as req_fire
                        req_fire.post(f"{FIREBASE_URL}/messages.json", json={
                            "liveSms": num,
                            "messageContent": msg,
                            "timestamp": int(time.time() * 1000)
                        })
                        done_ids.append(uid)
                        print(f"✅ SMS Masuk: {num} - {msg[:20]}")
            time.sleep(3) # Cek tiap 3 detik biar kenceng
        except: time.sleep(5)

# --- GET NUMBER (REQUESTER) ---
def tembak_get_number(range_num):
    api_url = "https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number"
    headers = {'content-type': 'application/json', 'cookie': MNIT_COOKIE, 'mauthtoken': MNIT_TOKEN, 'user-agent': MY_UA}
    try:
        res = requests.post(api_url, headers=headers, json={"range": range_num}, impersonate="chrome", timeout=30)
        if res.status_code == 200:
            data = res.json()
            # Ambil nomor dari data['data']['copy'] sesuai SS lo
            return data.get('data', {}).get('copy')
        return None
    except: return None

def run_xmnit():
    print("🚀 X-MNIT Engine Started...")
    # Jalankan Grabber SMS di background
    threading.Thread(target=grab_sms_mnit, daemon=True).start()
    
    while True:
        try:
            import requests as req_fire
            # Ambil perintah dari Firebase
            res = req_fire.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if res:
                for req_id, val in res.items():
                    target = val.get('range')
                    nomor = tembak_get_number(target)
                    if nomor:
                        # KIRIM KE /active_numbers (Biar Web lo liat)
                        req_fire.post(f"{FIREBASE_URL}/active_numbers.json", json={
                            "number": nomor,
                            "timestamp": int(time.time())
                        })
                        # Kirim Tele (Optional)
                        url_tele = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
                        req_fire.post(url_tele, data={'chat_id': TELE_CHAT_ID, 'text': f"✅ Nomor Didapat: {nomor}"})
                    
                    # Hapus perintah biar gak loop
                    req_fire.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(1.5)
        except: time.sleep(5)
