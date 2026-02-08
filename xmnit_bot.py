from curl_cffi import requests
import time, os, re

# DATA DARI KOYEB ENVIRONMENT
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
    # --- URL API ASLI HASIL TEMUAN TERAKHIR ---
    api_url = f"https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number?range={range_num}"
    
    headers = {
        'authority': 'x.mnitnetwork.com',
        'accept': 'application/json, text/plain, */*',
        'cookie': MNIT_COOKIE,
        'mauthtoken': MNIT_TOKEN, # Token rahasia MNIT
        'referer': 'https://x.mnitnetwork.com/mdashboard/getnum',
        'user-agent': MY_UA,      # Wajib sama dengan browser pas ambil cookie
        'x-requested-with': 'XMLHttpRequest',
    }
    
    try:
        # Tembak pake curl_cffi impersonate chrome biar gak kena Cloudflare
        res = requests.get(api_url, headers=headers, impersonate="chrome", timeout=30)
        
        print(f"DEBUG MNIT: Status {res.status_code}")
        
        if res.status_code == 200:
            raw_text = res.text.strip()
            print(f"ISI RESPON: {raw_text[:100]}") # Pantau 100 karakter pertama
            
            # 1. Jika isinya HTML (Cloudflare ngeblok lagi)
            if "<!DOCTYPE html>" in raw_text:
                return "CF_BLOCKED"
            
            # 2. Jika isinya angka doang (Target utama kita)
            if raw_text.isdigit() and 5 < len(raw_text) < 20:
                return raw_text
            
            # 3. Jika responnya JSON
            try:
                data = res.json()
                # Ambil field 'number' atau 'data.number'
                return data.get('number') or data.get('data', {}).get('number')
            except:
                # 4. Cari angka nomor (10-15 digit) pake Regex kalo isinya teks campur
                match = re.search(r'\d{10,15}', raw_text)
                return match.group(0) if match else None
                
        return "ERROR_" + str(res.status_code)
    except Exception as e:
        print(f"⚠️ Error API: {e}")
        return None

def run_xmnit():
    print("🚀 X-MNIT API Engine Started (mapi/v1)...")
    kirim_tele("🚀 Bot X-MNIT Stealth Aktif! Siap narik nomor 24 Jam.")
    
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
                            kirim_tele("⚠️ X-MNIT Gagal! Cloudflare mendeteksi bot. Update Cookie (cf_clearance) & User-Agent di Koyeb.")
                        elif nomor and "ERROR_" not in str(nomor):
                            # BERHASIL DAPET NOMOR!
                            # Kirim ke Firebase supaya muncul di Dashboard Web lo
                            req_fire.post(f"{FIREBASE_URL}/active_numbers.json", json={
                                "number": nomor,
                                "range": target,
                                "timestamp": int(time.time()),
                                "status": "active"
                            })
                            kirim_tele(f"✅ X-MNIT: Nomor Didapat!\n{nomor}")
                            print(f"✅ Berhasil: {nomor}")
                        else:
                            print(f"❌ Gagal ambil nomor. Respon: {nomor}")
                    
                    # Hapus perintah biar gak diproses terus-menerus
                    req_fire.delete(f"{FIREBASE_URL}/perintah_bot/{req_id}.json")
            
            time.sleep(1.5) # Cek Firebase tiap 1.5 detik
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(5)
