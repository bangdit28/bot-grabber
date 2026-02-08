import requests, time, os

MNIT_COOKIE = os.getenv("MNIT_COOKIE")
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

def kirim_tele(pesan):
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan})
    except: pass

def tembak_mnit(range_num):
    api_url = "https://x.mnitnetwork.com/api/v1/mdashboard/get"
    headers = {
        'Cookie': MNIT_COOKIE,
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0'
    }
    payload = {"range": range_num} # Nanti dicek lagi di tab Payload
    try:
        res = requests.post(api_url, json=payload, headers=headers, timeout=15)
        data = res.json()
        return data.get('number') or data.get('data', {}).get('number')
    except: return None

def run_xmnit():
    print("LOG: X-MNIT Listener Started...")
    while True:
        try:
            req = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if req:
                for req_id, val in req.items():
                    target = val.get('range')
                    nomor = tembak_mnit(target)
                    if nomor:
                        # Kirim ke Firebase di path yang dibaca UI lo (misal: active_numbers)
                        requests.post(f"{FIREBASE_URL}/active_numbers.json", json={"number": nomor})
                        kirim_tele(f"✅ X-MNIT: Nomor Didapat!\n{nomor}")
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(1.5)
        except: time.sleep(5)
