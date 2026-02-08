from curl_cffi import requests as curl_req
import requests as normal_req
import time, os, threading, re

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
    except: pass

def grab_sms_mnit():
    print("LOG: SMS Grabber X-MNIT Aktif (Mode Brutal)...")
    done_ids = []
    
    headers = {
        'cookie': MNIT_COOKIE,
        'mauthtoken': MNIT_TOKEN,
        'user-agent': MY_UA,
        'accept': 'application/json',
        'x-requested-with': 'XMLHttpRequest'
    }

    while True:
        # CEK TANGGAL 08 DAN 09 (Server MNIT telat tanggalnya)
        for tgl in ["2026-02-08", "2026-02-09"]:
            api_info = f"https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?date={tgl}&page=1&search=&status="
            try:
                res = curl_req.get(api_info, headers=headers, impersonate="chrome", timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    # Ambil list data (biasanya di data['data']['data'])
                    items = data.get('data', {}).get('data', [])
                    
                    if not items: continue # Loncat kalo kosong
                    
                    for item in items:
                        num = item.get('copy') # Nomor HP (+232...)
                        code = item.get('code') # OTP (Angka doang)
                        
                        if code and num:
                            # Bersihkan tag HTML (biasanya code warna ijo ada <span>)
                            clean_code = re.sub('<[^<]+?>', '', str(code)).strip()
                            if not clean_code or len(clean_code) < 3: continue
                            
                            uid = f"{num}_{clean_code}"
                            if uid not in done_ids:
                                print(f"🔥 KODE DITEMUKAN: {num} -> {clean_code}")
                                msg_content = f"<#> {clean_code} is your Facebook code"
                                
                                # 1. KIRIM KE FIREBASE
                                normal_req.post(f"{FIREBASE_URL}/messages.json", json={
                                    "liveSms": num,
                                    "messageContent": msg_content,
                                    "timestamp": int(time.time() * 1000)
                                })
                                # 2. KIRIM KE TELEGRAM
                                kirim_tele(f"📩 OTP MNIT MASUK!\nNomor: {num}\nKode: {clean_code}")
                                done_ids.append(uid)
            except:
                pass
        time.sleep(2) # Cek tiap 2 detik biar super fast

def tembak_get_number(range_num):
    api_url = "https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number"
    headers = {'content-type': 'application/json','cookie': MNIT_COOKIE,'mauthtoken': MNIT_TOKEN,'user-agent': MY_UA}
    try:
        res = curl_req.post(api_url, headers=headers, json={"range": range_num}, impersonate="chrome", timeout=30)
        if res.status_code == 200:
            return res.json().get('data', {}).get('copy')
    except: return None

def run_xmnit():
    print("🚀 X-MNIT Engine Started...")
    kirim_tele("🚀 Bot X-MNIT Aktif! PC Boleh Mati Sekarang.")
    threading.Thread(target=grab_sms_mnit, daemon=True).start()
    
    while True:
        try:
            perintah = normal_req.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if perintah:
                for req_id, val in perintah.items():
                    target = val.get('range')
                    nomor = tembak_get_number(target)
                    if nomor:
                        normal_req.post(f"{FIREBASE_URL}/active_numbers.json", json={"number": nomor, "timestamp": int(time.time())})
                        kirim_tele(f"✅ Nomor Didapat: {nomor}")
                    normal_req.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(1.5)
        except: time.sleep(5)

if __name__ == "__main__":
    run_xmnit()
