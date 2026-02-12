import threading, time, os, re, random, requests, json
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_req

# === CONFIG ===
FIREBASE_URL = os.getenv("FIREBASE_URL", "").strip().rstrip('/')
MY_COOKIE = os.getenv("MY_COOKIE", "").strip()
MNIT_COOKIE = os.getenv("MNIT_COOKIE", "").strip()
MNIT_TOKEN = os.getenv("MNIT_TOKEN", "").strip()
MY_UA = os.getenv("MY_UA", "").strip()
TELE_TOKEN = os.getenv("TELE_TOKEN", "").strip()
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID", "").strip()

sudah_diproses = set()

def detect_app(text):
    apps = ['Facebook', 'WhatsApp', 'Telegram', 'Google', 'TikTok', 'Instagram', 'Shopee', 'Gojek']
    for app in apps:
        if app.lower() in text.lower(): return app
    if 'fb' in text.lower(): return 'Facebook'
    if 'wa' in text.lower(): return 'WhatsApp'
    return "Global App"

def kirim_tele(pesan):
    if not TELE_TOKEN or not TELE_CHAT_ID: return
    try:
        otp_match = re.search(r'\d{4,8}', pesan)
        clean_msg = pesan
        if otp_match:
            otp = otp_match.group(0)
            clean_msg = pesan.replace(otp, f"<code>{otp}</code>")
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': clean_msg, 'parse_mode': 'HTML'}, timeout=10)
    except: pass

# ==========================================
# 1. MANAGER: AMBIL NOMOR (SILENT)
# ==========================================
def run_manager():
    print("🚀 MANAGER: Antrian Active...")
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
                nama_service = item.get('serviceName') or item.get('name') or "Unknown"
                app_name = detect_app(nama_service)

                if "PREFIX" not in str(item.get('type')).upper():
                    nums = item.get('stock') or item.get('stok') or []
                    if nums:
                        if isinstance(nums, list):
                            nomor_hasil = nums.pop(0)
                            requests.put(f"{FIREBASE_URL}/inventory/{inv_id}/stock.json", json=nums)
                        else:
                            key = list(nums.keys())[0]; nomor_hasil = nums[key]
                            requests.delete(f"{FIREBASE_URL}/inventory/{inv_id}/stock/{key}.json")
                else:
                    target_range = item.get('prefixes') or item.get('prefix') or "2367261XXXX"
                    h = {'content-type':'application/json','cookie':MNIT_COOKIE,'mauthtoken':MNIT_TOKEN,'user-agent':MY_UA}
                    res_x = curl_req.post("https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number", headers=h, json={"range":target_range}, impersonate="chrome", timeout=20)
                    if res_x.status_code == 200: nomor_hasil = res_x.json().get('data', {}).get('copy')

                if nomor_hasil:
                    clean_n = re.sub(r'\D', '', str(nomor_hasil))
                    data_final = {
                        "number": str(nomor_hasil), "name": m_name, "country": nama_service,
                        "cli_app": app_name, "timestamp": int(time.time() * 1000)
                    }
                    requests.patch(f"{FIREBASE_URL}/members/{m_id}/active_numbers/{clean_n}.json", json=data_final)
                    requests.patch(f"{FIREBASE_URL}/active_numbers_lookup/{clean_n}.json", json=data_final)
            
            if len(sudah_diproses) > 100: sudah_diproses.clear()
            time.sleep(1)
        except: time.sleep(5)

# ==========================================
# 2. GRABBER: SMS (FIX TOTAL CALLTIME)
# ==========================================
def process_incoming_sms(num, msg, situs_asal):
    try:
        # Ambil angka saja dari nomor (paling akurat buat sinkronisasi)
        clean_num = re.sub(r'\D', '', str(num))
        owner = requests.get(f"{FIREBASE_URL}/active_numbers_lookup/{clean_num}.json").json()
        
        if owner:
            app_name = owner.get('cli_app') or detect_app(msg)
            # Bersihkan pesan dari u003c (HTML tag mentah)
            clean_msg = msg.replace('u003c#u003e', '<#>').strip()

            text_tele = (
                f"📩 <b>SMS MASUK!</b>\n\n"
                f"👤 <b>Nama :</b> {owner['name']}\n"
                f"📱 <b>Nomor :</b> <code>{owner['number']}</code>\n"
                f"🌍 <b>Negara :</b> {owner['country']}\n"
                f"📌 <b>CLI atau Apps :</b> {app_name}\n"
                f"💬 <b>Pesan :</b> {clean_msg}"
            )
            kirim_tele(text_tele)
            
            # Update ke Web
            requests.post(f"{FIREBASE_URL}/messages.json", json={"liveSms": owner['number'], "messageContent": clean_msg, "timestamp": int(time.time() * 1000)})
            # Hapus biar gak double notif
            requests.delete(f"{FIREBASE_URL}/active_numbers_lookup/{clean_num}.json")
            print(f"✅ SMS {clean_num} Grabbed!")
    except: pass

def run_grabber():
    print("📡 GRABBER: Scanning OTP...")
    done_ids = set()
    h_mnit = {'cookie': MNIT_COOKIE,'mauthtoken': MNIT_TOKEN,'user-agent': MY_UA,'accept': 'application/json','x-requested-with': 'XMLHttpRequest'}
    
    while True:
        try:
            # --- 🛰️ GRAB CALLTIME (FUNGSI BARU) ---
            res_ct = requests.get(f"https://www.calltimepanel.com/yeni/SMS/?_={int(time.time()*1000)}", headers={'Cookie': MY_COOKIE}, timeout=15)
            if res_ct.status_code == 200:
                soup = BeautifulSoup(res_ct.text, 'html.parser')
                for r in soup.select('table tr'):
                    tds = r.find_all('td')
                    if len(tds) < 4: continue
                    
                    # AMBIL NOMOR PAKE REGEX (Cari angka minimal 8 digit di kolom Reciever)
                    raw_reciever = tds[1].text.strip()
                    num_match = re.findall(r'\d{8,15}', raw_reciever)
                    if not num_match: continue
                    n = num_match[-1] # Ambil angka terakhir di baris itu
                    
                    m = tds[2].text.strip()
                    uid = f"{n}_{m[:15]}"
                    
                    if uid not in done_ids:
                        process_incoming_sms(n, m, "CallTime")
                        done_ids.append(uid)

            # --- 📡 GRAB X-MNIT ---
            tgl = time.strftime("%Y-%m-%d")
            url_mn = f"https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?date={tgl}&page=1&search=&status="
            res_mn = curl_req.get(url_mn, headers=h_mnit, impersonate="chrome", timeout=15)
            if res_mn.status_code == 200:
                data = res_mn.json()
                items = data.get('data', {}).get('numbers', [])
                for it in items:
                    num, otp_raw = it.get('number'), it.get('otp')
                    if num and otp_raw and "Waiting" not in otp_raw:
                        c_code = re.sub('<[^<]+?>', '', str(otp_raw)).strip()
                        uid = f"{num}_{c_code[:10]}"
                        if uid not in done_ids:
                            process_incoming_sms(num, c_code, "x.mnitnetwork")
                            done_ids.add(uid)
            
            if len(done_ids) > 200: done_ids.clear()
            time.sleep(4)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_manager, daemon=True).start()
    threading.Thread(target=run_grabber, daemon=True).start()
    while True: time.sleep(10)
