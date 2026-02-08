from curl_cffi import requests
import time, os, re

FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
MY_UA = os.getenv("MY_UA")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

scraper = cloudscraper.create_scraper(browser={'browser': 'chrome','platform': 'windows','mobile': False}) if 'cloudscraper' in globals() else requests

def kirim_tele(pesan):
    try:
        import requests as req_tele
        req_tele.post(f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage", data={'chat_id': TELE_CHAT_ID, 'text': pesan}, timeout=5)
    except: pass

# --- FUNGSI AMBIL NOMOR (REQUESTER) ---
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
        res = requests.post(api_url, headers=headers, json={"range": range_num}, impersonate="chrome", timeout=30)
        if res.status_code == 200:
            data = res.json()
            return data.get('data', {}).get('copy')
        return None
    except: return None

# --- FUNGSI AMBIL SMS DARI X-MNIT (GRABBER) ---
def grab_sms_mnit():
    # URL Console X-MNIT buat liat SMS masuk
    console_url = "https://x.mnitnetwork.com/mapi/v1/mdashboard/console" 
    headers = {'cookie': MNIT_COOKIE, 'mauthtoken': MNIT_TOKEN, 'user-agent': MY_UA}
    done_ids = []
    
    while True:
        try:
            res = requests.get(console_url, headers=headers, impersonate="chrome", timeout=30)
            if res.status_code == 200:
                data = res.json()
                # Asumsi MNIT ngasih list SMS di dalam data['sms_list'] atau sejenisnya
                # Kita sesuaikan dengan struktur mereka
                items = data.get('data', [])
                for item in items:
                    # Sesuaikan nama field (msg, sender, date)
                    msg = item.get('message') or item.get('text')
                    sender = item.get('sender') or item.get('from')
                    num_target = item.get('phone') # Nomor kita
                    
                    uid = f"{num_target}_{msg[:10]}"
                    if uid not in done_ids and msg:
                        # Kirim ke Firebase supaya muncul di Web lo
                        requests.post(f"{FIREBASE_URL}/messages.json", json={
                            "liveSms": num_target,
                            "messageContent": msg,
                            "timestamp": int(time.time())
                        })
                        kirim_tele(f"📩 SMS BARU (X-MNIT)!\nKe: {num_target}\nMsg: {msg}")
                        done_ids.append(uid)
            time.sleep(5) # Cek SMS tiap 5 detik
        except: time.sleep(10)

# --- FUNGSI PANTAU PERINTAH WEB ---
def run_xmnit():
    print("🚀 X-MNIT Engine Active (Request + Grabber)...")
    # Jalankan Grabber SMS di background thread
    import threading
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
                            "number": nomor, "range": target, "status": "active", "timestamp": int(time.time())
                        })
                        kirim_tele(f"✅ X-MNIT: Nomor Didapat!\n{nomor}")
                    req_fire.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(2)
        except: time.sleep(5)
