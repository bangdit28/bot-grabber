from curl_cffi import requests
import time, os, re

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
        req_tele.post(f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage", 
                      data={'chat_id': TELE_CHAT_ID, 'text': pesan}, timeout=5)
    except: pass

def tembak_get_number(range_num):
    # --- URL API (TANPA ?range= karena kita pake POST) ---
    api_url = "https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number"
    
    headers = {
        'authority': 'x.mnitnetwork.com',
        'accept': 'application/json, text/plain, */*',
        'content-type': 'application/json', # WAJIB ADA BUAT POST
        'cookie': MNIT_COOKIE,
        'mauthtoken': MNIT_TOKEN,
        'referer': 'https://x.mnitnetwork.com/mdashboard/getnum',
        'user-agent': MY_UA,
        'origin': 'https://x.mnitnetwork.com',
        'x-requested-with': 'XMLHttpRequest',
    }
    
    # DATA DIKIRIM LEWAT BODY JSON
    payload = {
        "range": range_num
    }
    
    try:
        # GANTI JADI requests.post
        res = requests.post(api_url, headers=headers, json=payload, impersonate="chrome", timeout=30)
        
        print(f"DEBUG MNIT: Status {res.status_code}")
        
        if res.status_code == 200:
            raw_text = res.text.strip()
            print(f"ISI RESPON: {raw_text[:100]}")
            
            if "<!DOCTYPE html>" in raw_text:
                return "CF_BLOCKED"
            
            # Jika respon angka langsung
            if raw_text.isdigit() and 5 < len(raw_text) < 20:
                return raw_text
                
            try:
                data = res.json()
                # Sesuaikan field 'number' berdasarkan hasil Preview Network lo
                return data.get('number') or data.get('data', {}).get('number')
            except:
                match = re.search(r'\d{10,15}', raw_text)
                return match.group(0) if match else None
                
        return "ERROR_" + str(res.status_code)
    except Exception as e:
        print(f"⚠️ Error API: {e}")
        return None

def run_xmnit():
    print("🚀 X-MNIT API Engine Started (POST Mode)...")
    
    while True:
        try:
            import requests as req_fire
            res_fire = req_fire.get(f"{FIREBASE_URL}/perintah_bot.json")
            req = res_fire.json()
            
            if req:
                for req_id, val in req.items():
                    target = val.get('range')
                    if target:
                        print(f"🚀 Memproses Range: {target}")
                        nomor = tembak_get_number(target)
                        
                        if nomor == "CF_BLOCKED":
                            kirim_tele("⚠️ Cloudflare Blokir! Ambil COOKIE baru (cf_clearance) dari F12.")
                        elif nomor and "ERROR_" not in str(nomor):
                            req_fire.post(f"{FIREBASE_URL}/active_numbers.json", json={
                                "number": nomor,
                                "range": target,
                                "timestamp": int(time.time()),
                                "status": "active"
                            })
                            kirim_tele(f"✅ X-MNIT: Nomor Didapat!\n{nomor}")
                        else:
                            print(f"❌ Gagal. Kode Respon: {nomor}")
                    
                    req_fire.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            time.sleep(1.5)
        except Exception as e:
            time.sleep(5)
