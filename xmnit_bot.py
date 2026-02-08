import requests, time, os, threading
from curl_cffi import requests as curl_req

# CONFIG
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
MY_UA = os.getenv("MY_UA")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

def kirim_tele(pesan):
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan}, timeout=5)
    except: pass

# --- FUNGSI AMBIL NOMOR ---
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
            return data.get('data', {}).get('copy')
        return None
    except: return None

# --- FUNGSI GRAB SMS X-MNIT ---
def grab_sms_mnit():
    print("LOG: Grabber SMS X-MNIT Aktif...")
    # URL Console X-MNIT buat cek SMS masuk
    url_sms = "https://x.mnitnetwork.com/mapi/v1/mdashboard/console"
    headers = {'cookie': MNIT_COOKIE, 'mauthtoken': MNIT_TOKEN, 'user-agent': MY_UA}
    done_ids = []

    while True:
        try:
            res = curl_req.get(url_sms, headers=headers, impersonate="chrome", timeout=30)
            if res.status_code == 200:
                data = res.json()
                # Sesuaikan 'items' dengan struktur asli MNIT (berdasarkan tab Preview lo)
                items = data.get('data', []) 
                for item in items:
                    msg = item.get('message') or item.get('text')
                    num = item.get('phone') or item.get('number')
                    date = item.get('date') or str(int(time.time()))

                    if not msg or not num: continue

                    uid = f"{num}_{msg[:15]}"
                    if uid not in done_ids:
                        # SIMPAN KE FIREBASE (Format harus sama dengan CallTime)
                        requests.post(f"{FIREBASE_URL}/messages.json", json={
                            "liveSms": num, # Ini kunci biar muncul di Web lo
                            "messageContent": msg,
                            "smsDate": date,
                            "timestamp": int(time.time() * 1000)
                        })
                        kirim_tele(f"📩 SMS MNIT!\nKe: {num}\nIsi: {msg}")
                        done_ids.append(uid)
            time.sleep(4) # Cek tiap 4 detik
        except: time.sleep(10)

# --- FUNGSI UTAMA ---
def run_xmnit():
    print("🚀 X-MNIT Engine Started...")
    
    # Jalankan Grabber SMS di background
    threading.Thread(target=grab_sms_mnit, daemon=True).start()
    
    while True:
        try:
            # Pantau perintah Get Number dari Web App
            res = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if res:
                for req_id, val in res.items():
                    target = val.get('range')
                    nomor = tembak_get_number(target)
                    
                    if nomor:
                        # BERHASIL: Simpan ke folder /active_numbers
                        requests.post(f"{FIREBASE_URL}/active_numbers.json", json={
                            "number": nomor,
                            "range": target,
                            "timestamp": int(time.time()),
                            "status": "active"
                        })
                        kirim_tele(f"✅ Nomor Didapat: {nomor}")
                    
                    # Hapus perintah biar gak diproses terus
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(2)
        except: time.sleep(5)
