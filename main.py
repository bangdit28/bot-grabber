import threading, time, os, re, random, requests, json
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_req

# === CONFIGURATION ===
FIREBASE_URL = os.getenv("FIREBASE_URL", "").strip().rstrip('/')
MY_COOKIE = os.getenv("MY_COOKIE", "").strip()
MNIT_COOKIE = os.getenv("MNIT_COOKIE", "").strip()
MNIT_TOKEN = os.getenv("MNIT_TOKEN", "").strip()
MY_UA = os.getenv("MY_UA", "").strip()
TELE_TOKEN = os.getenv("TELE_TOKEN", "").strip()
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID", "").strip()

sudah_diproses = set()

def detect_app(text):
    """Otomatis deteksi aplikasi dari pesan atau nama layanan"""
    apps = ['Facebook', 'WhatsApp', 'Telegram', 'Google', 'TikTok', 'Instagram', 'Shopee', 'Gojek']
    for app in apps:
        if app.lower() in text.lower(): return app
    if 'fb' in text.lower(): return 'Facebook'
    if 'wa' in text.lower(): return 'WhatsApp'
    return "Global App"

def kirim_tele(pesan):
    if not TELE_TOKEN or not TELE_CHAT_ID: return
    try:
        # OTP monospaced biar tinggal klik salin
        otp_match = re.search(r'\d{4,8}', pesan)
        if otp_match:
            otp = otp_match.group(0)
            pesan = pesan.replace(otp, f"<code>{otp}</code>")
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': pesan, 'parse_mode': 'HTML'}, timeout=10)
    except: pass

def get_only_digits(text):
    """Hanya mengambil angka (buang spasi, +, -, strip)"""
    return re.sub(r'\D', '', str(text))

# ==========================================
# 1. MANAGER: AMBIL NOMOR (STOK & PREFIX)
# ==========================================
def run_manager():
    print("🚀 MANAGER: Antrian Online...")
    while True:
        try:
            r = requests.get(f"{FIREBASE_URL}/perintah_bot.json")
            cmds = r.json()
            if not cmds or not isinstance(cmds, dict):
                time.sleep(1); continue
            
            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()
            for cmd_id, val in cmds.items():
                if cmd_id in sudah_diproses: continue
                sudah_diproses.add(cmd_id)
                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
                
                m_id, m_name, inv_id = val.get('memberId'), val.get('memberName', 'User'), val.get('inventoryId')
                item = inv.get(inv_id) if inv else None
                if not item: continue

                nomor_hasil = None
                service_name = item.get('serviceName') or item.get('name') or "Layanan"
                country_name = item.get('countryName') or "Global"
                
                # --- LOGIKA AMBIL MANUAL (CALLTIME) ---
                if item.get('stock'):
                    nums = item.get('stock')
                    if isinstance(nums, list) and len(nums) > 0:
                        nomor_hasil = nums.pop(0)
                        requests.put(f"{FIREBASE_URL}/inventory/{inv_id}/stock.json", json=nums)
                    elif isinstance(nums, dict) and len(nums) > 0:
                        key = list(nums.keys())[0]; nomor_hasil = nums[key]
                        requests.delete(f"{FIREBASE_URL}/inventory/{inv_id}/stock/{key}.json")
                
                # --- LOGIKA AMBIL PREFIX (X-MNIT) ---
                elif item.get('prefixes'):
                    target_range = item.get('prefixes')
                    h = {'content-type':'application/json','cookie':MNIT_COOKIE,'mauthtoken':MNIT_TOKEN,'user-agent':MY_UA}
                    res_x = curl_req.post("https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number", headers=h, json={"range":target_range}, impersonate="chrome", timeout=20)
                    if res_x.status_code == 200: nomor_hasil = res_x.json().get('data', {}).get('copy')

                if nomor_hasil:
                    clean_n = get_only_digits(nomor_hasil)
                    data_final = {
                        "number": str(nomor_hasil), "name": m_name, "country": country_name,
                        "cli_app": detect_app(service_name), "timestamp": int(time.time() * 1000)
                    }
                    # Update Web Anggota & Lookup
                    requests.patch(f"{FIREBASE_URL}/members/{m_id}/active_numbers/{clean_n}.json", json=data_final)
                    requests.patch(f"{FIREBASE_URL}/active_numbers_lookup/{clean_n}.json", json=data_final)
                    print(f"✅ Nomor {nomor_hasil} dikirim ke {m_name}")

            if len(sudah_diproses) > 100: sudah_diproses.clear()
            time.sleep(1)
        except: time.sleep(5)

# ==========================================
# 2. GRABBER: SMS (FIX CALLTIME & X-MNIT)
# ==========================================
def process_incoming_sms(num, msg):
    try:
        clean_num = get_only_digits(num)
        # Cari siapa yang pegang nomor ini
        owner = requests.get(f"{FIREBASE_URL}/active_numbers_lookup/{clean_num}.json").json()
        if owner:
            # Bersihkan pesan dari HTML entities mentah
            clean_msg = msg.replace('u003c#u003e', '<#>').replace('u003e', '>').strip()
            
            text_tele = (f"📩 <b>SMS MASUK!</b>\n\n"
                        f"👤 <b>Nama :</b> {owner['name']}\n"
                        f"📱 <b>Nomor :</b> <code>{owner['number']}</code>\n"
                        f"🌍 <b>Negara :</b> {owner['country']}\n"
                        f"📌 <b>CLI atau Apps :</b> {owner.get('cli_app', 'Global App')}\n"
                        f"💬 <b>Pesan :</b> {clean_msg}")
            kirim_tele(text_tele)
            
            # Post ke Web lo agar list update
            requests.post(f"{FIREBASE_URL}/messages.json", json={"liveSms": owner['number'], "messageContent": clean_msg, "timestamp": int(time.time() * 1000)})
            # Hapus lookup biar gak dobel notif
            requests.delete(f"{FIREBASE_URL}/active_numbers_lookup/{clean_num}.json")
            print(f"✅ SMS {clean_num} Sukses Grabbed!")
    except: pass

def run_grabber():
    print("📡 GRABBER: Scanning OTP...")
    done_ids = set()
    h_mnit = {'cookie': MNIT_COOKIE,'mauthtoken': MNIT_TOKEN,'user-agent': MY_UA,'accept': 'application/json','x-requested-with': 'XMLHttpRequest'}
    
    while True:
        try:
            # --- 🛰️ SCAN CALLTIME (Pasti Nyangkut) ---
            res_ct = requests.get("https://www.calltimepanel.com/yeni/SMS/", headers={'Cookie': MY_COOKIE}, timeout=15)
            if res_ct.status_code == 200:
                soup = BeautifulSoup(res_ct.text, 'html.parser')
                for r in soup.select('table tr'):
                    tds = r.find_all('td')
                    if len(tds) < 4: continue
                    # Ambil angka nomor HP-nya saja dari kolom Reciever
                    raw_n = tds[1].text.strip()
                    digits = get_only_digits(raw_n)
                    if len(digits) < 8: continue
                    
                    m = tds[2].text.strip()
                    uid = f"ct_{digits}_{m[:10]}"
                    if uid not in done_ids:
                        process_incoming_sms(digits, m)
                        done_ids.add(uid)

            # --- 📡 SCAN X-MNIT (Tetap Work) ---
            tgl = time.strftime("%Y-%m-%d")
            url_mn = f"https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?date={tgl}&page=1&search=&status="
            res_mn = curl_req.get(url_mn, headers=h_mnit, impersonate="chrome", timeout=15)
            if res_mn.status_code == 200:
                data_mnit = res_mn.json()
                items = data_mnit.get('data', {}).get('numbers', [])
                for it in items:
                    num, otp_raw = it.get('number'), it.get('otp')
                    if num and otp_raw and "Waiting" not in otp_raw:
                        c_code = re.sub('<[^<]+?>', '', str(otp_raw)).strip()
                        uid = f"mn_{num}_{c_code[:10]}"
                        if uid not in done_ids:
                            process_incoming_sms(num, c_code)
                            done_ids.add(uid)
            
            if len(done_ids) > 500: done_ids.clear()
            time.sleep(3)
        except: time.sleep(5)

if __name__ == "__main__":
    url_tele = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    requests.post(url_tele, data={'chat_id': TELE_CHAT_ID, 'text': "🚀 <b>BOT SINKRON AKTIF!</b>\nCallTime & X-MNIT Standby.", 'parse_mode': 'HTML'})
    threading.Thread(target=run_manager, daemon=True).start()
    threading.Thread(target=run_grabber, daemon=True).start()
    while True: time.sleep(10)
