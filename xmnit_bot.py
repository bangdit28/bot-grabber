from curl_cffi import requests
import time, os

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
        # Gunakan requests biasa buat tele gak apa-apa
        import requests as req_tele
        req_tele.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan}, timeout=5)
    except: pass

def tembak_get_number(range_num):
    api_url = f"https://x.mnitnetwork.com/mdashboard/getnum?range={range_num}"
    
    headers = {
        'authority': 'x.mnitnetwork.com',
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
        'cookie': MNIT_COOKIE,
        'mauthtoken': MNIT_TOKEN,
        'referer': 'https://x.mnitnetwork.com/mauth/dashboard',
        'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': MY_UA,
        'x-requested-with': 'XMLHttpRequest',
    }
    
    try:
        # KUNCI UTAMA: impersonate='chrome' bikin TLS Fingerprint bot lo SAMA PERSIS sama Chrome asli
        res = requests.get(api_url, headers=headers, impersonate="chrome", timeout=30)
        
        print(f"DEBUG MNIT: {res.status_code}")

        if res.status_code == 200:
            if "Just a moment" in res.text:
                return "CF_BLOCKED"
            
            # Jika respon pendek (nomor)
            if 5 < len(res.text) < 25:
                return res.text.strip()
            
            try:
                data = res.json()
                return data.get('number') or data.get('data', {}).get('number')
            except:
                return None
        return "ERROR_" + str(res.status_code)
    except Exception as e:
        print(f"⚠️ Error: {e}")
        return None

def run_xmnit():
    print("🚀 X-MNIT Stealth Mode Started...")
    kirim_tele("🚀 Bot X-MNIT Stealth Aktif! PC Boleh Mati.")
    
    while True:
        try:
            # Ambil perintah dari Firebase
            import requests as req_fire
            res_fire = req_fire.get(f"{FIREBASE_URL}/perintah_bot.json")
            req = res_fire.json()
            
            if req:
                for req_id, val in req.items():
                    target = val.get('range')
                    if target:
                        print(f"🚀 Proses Range: {target}")
                        nomor = tembak_get_number(target)
                        
                        if nomor == "CF_BLOCKED":
                            kirim_tele("⚠️ Cloudflare mendeteksi Bot! Coba ambil Cookie baru & pastikan saldo ada.")
                        elif nomor and "ERROR_" not in str(nomor):
                            # BERHASIL
                            req_fire.post(f"{FIREBASE_URL}/active_numbers.json", json={
                                "number": nomor,
                                "range": target,
                                "timestamp": int(time.time())
                            })
                            kirim_tele(f"✅ X-MNIT: Nomor Didapat!\n{nomor}")
                        else:
                            print(f"❌ Gagal dapet nomor. Respon: {nomor}")
                    
                    # Hapus perintah biar gak looping
                    req_fire.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            
            time.sleep(2)
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(5)
