import threading, time, os, re, random, requests, json
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_req

# === CONFIGURATION (SET DI KOYEB) ===
FIREBASE_URL = os.getenv("FIREBASE_URL", "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app").strip().rstrip('/')
MY_COOKIE = os.getenv("MY_COOKIE", "").strip()      # Cookie CallTime
MNIT_COOKIE = os.getenv("MNIT_COOKIE", "").strip()  # Cookie X-MNIT
MNIT_TOKEN = os.getenv("MNIT_TOKEN", "").strip()    # Mauthtoken X-MNIT
MY_UA = os.getenv("MY_UA", "").strip()              # User Agent Asli
TELE_TOKEN = os.getenv("TELE_TOKEN", "").strip()
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID", "").strip()

# Cegah proses ganda saat klik
sudah_diproses = set()

def kirim_tele(pesan):
    if not TELE_TOKEN or not TELE_CHAT_ID: return
    try:
        # OTP monospaced biar tinggal klik salin
        otp_match = re.search(r'\d{4,8}', pesan)
        clean_msg = pesan
        if otp_match:
            otp = otp_match.group(0)
            clean_msg = pesan.replace(otp, f"<code>{otp}</code>")
        
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': clean_msg, 'parse_mode': 'HTML'}, timeout=10)
    except: pass

# ==========================================
# 1. MANAGER: AMBIL NOMOR (SINKRON STOK & PREFIX)
# ==========================================
def run_manager():
    print("🚀 MANAGER: Antrian Multi-Panel Active...")
    while True:
        try:
            # Ambil antrian perintah dari Firebase
            r = requests.get(f"{FIREBASE_URL}/perintah_bot.json")
            cmds = r.json()
            if not cmds or not isinstance(cmds, dict):
                time.sleep(1.5); continue
            
            # Ambil Inventory (Gudang Stok/Prefix)
            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()
            
            for cmd_id, val in cmds.items():
                if cmd_id in sudah_diproses: continue
                sudah_diproses.add(cmd_id)
                
                # Langsung hapus biar web gak muter lama
                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
                
                m_id = val.get('memberId')
                m_name = val.get('memberName', 'User')
                inv_id = val.get('inventoryId')
                
                item = inv.get(inv_id) if inv else None
                if not item: continue

                nomor_hasil = None
                situs = "CallTime"
                
                # --- LOGIKA AMBIL NOMOR ---
                if "PREFIX" not in str(item.get('type')).upper():
                    # Ambil dari STOK MANUAL (CallTime)
                    nums = item.get('stock') or item.get('stok') or []
                    if nums:
                        if isinstance(nums, list):
                            nomor_hasil = nums.pop(0)
                            requests.put(f"{FIREBASE_URL}/inventory/{inv_id}/stock.json", json=nums)
                        else:
                            key = list(nums.keys())[0]; nomor_hasil = nums[key]
                            requests.delete(f"{FIREBASE_URL}/inventory/{inv_id}/stock/{key}.json")
                else:
                    # Ambil dari PREFIX (X-MNIT)
                    situs = "x.mnitnetwork"
                    target_range = item.get('prefixes') or item.get('prefix') or "2367261XXXX"
                    h = {'content-type':'application/json','cookie':MNIT_COOKIE,'mauthtoken':MNIT_TOKEN,'user-agent':MY_UA}
                    res_x = curl_req.post("https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number", headers=h, json={"range":target_range}, impersonate="chrome", timeout=20)
                    if res_x.status_code == 200:
                        nomor_hasil = res_x.json().get('data', {}).get('copy')

                if nomor_hasil:
                    # Bersihkan nomor untuk lookup
                    clean_n = re.sub(r'\D', '', str(nomor_hasil))
                    data_final = {
                        "number": str(nomor_hasil),
                        "name": m_name,
                        "country": item.get('serviceName') or item.get('name'),
                        "situs": situs,
                        "timestamp": int(time.time() * 1000)
                    }
                    # Simpan ke web dashboard anggota & lookup SMS
                    requests.patch(f"{FIREBASE_URL}/members/{m_id}/active_numbers/{clean_n}.json", json=data_final)
                    requests.patch(f"{FIREBASE_URL}/active_numbers_lookup/{clean_n}.json", json=data_final)
                    
                    # Notif Telegram Berhasil Ambil Nomor
                    kirim_tele(f"✅ <b>NOMOR DIDAPAT!</b>\n👤 Nama : {m_name}\n📱 Nomor : <code>{nomor_hasil}</code>\n🌍 Negara : {data_final['country']}\n📌 Situs : {situs}")

            if len(sudah_diproses) > 100: sudah_diproses.clear()
            time.sleep(1)
        except Exception as e:
            print(f"Error Manager: {e}"); time.sleep(5)

# ==========================================
# 2. GRABBER: SCANNIG SMS (CALLTIME + MNIT)
# ==========================================
def process_sms_logic(num, msg, asal):
    try:
        clean_num = re.sub(r'\D', '', str(num))
        # Cari siapa pemilik nomor ini
        owner = requests.get(f"{FIREBASE_URL}/active_numbers_lookup/{clean_num}.json").json()
        if owner:
            # Notif Telegram SMS Masuk
            text_tele = (f"📩 <b>SMS BARU!</b>\n\n👤 Nama : {owner['name']}\n"
                         f"📱 Nomor : <code>{owner['number']}</code>\n🌍 Negara : {owner['country']}\n"
                         f"💬 Pesan : {msg}")
            kirim_tele(text_tele)
            
            # Update Dashboard Web
            requests.post(f"{FIREBASE_URL}/messages.json", json={"liveSms": owner['number'], "messageContent": msg, "timestamp": int(time.time() * 1000)})
            # Hapus biar gak double notif
            requests.delete(f"{FIREBASE_URL}/active_numbers_lookup/{clean_num}.json")
            print(f"✅ SMS {asal} Grabbed: {clean_num}")
    except: pass

def run_grabber():
    print("📡 GRABBER: Scanning OTP Dual-Panel...")
    done_ids = set()
    h_mnit = {'cookie': MNIT_COOKIE,'mauthtoken': MNIT_TOKEN,'user-agent': MY_UA,'accept': 'application/json','x-requested-with': 'XMLHttpRequest'}
    
    while True:
        try:
            # --- 🛰️ SCAN CALLTIME ---
            res_ct = requests.get(f"https://www.calltimepanel.com/yeni/SMS/?_={int(time.time()*1000)}", headers={'Cookie': MY_COOKIE}, timeout=15)
            if "login" not in res_ct.url:
                soup = BeautifulSoup(res_ct.text, 'html.parser')
                for r in soup.select('table tr'):
                    tds = r.find_all('td')
                    if len(tds) < 4: continue
                    # Ambil nomor (biasanya format: Negara - Nomor)
                    raw_n = tds[1].text.strip()
                    m = tds[2].text.strip()
                    uid = f"{raw_n}_{m[:10]}"
                    if uid not in done_ids:
                        process_sms_logic(raw_n, m, "CallTime")
                        done_ids.add(uid)

            # --- 📡 SCAN X-MNIT (API mapi/v1) ---
            tgl = time.strftime("%Y-%m-%d")
            url_mn = f"https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?date={tgl}&page=1&search=&status="
            res_mn = curl_req.get(url_mn, headers=h_mnit, impersonate="chrome", timeout=15)
            if res_mn.status_code == 200:
                data = res_mn.json().get('data', {}).get('numbers', [])
                for it in data:
                    num, otp_raw = it.get('number'), it.get('otp')
                    if num and otp_raw and "Waiting" not in otp_raw:
                        # Bersihkan tag HTML ijo dari kode
                        clean_c = re.sub('<[^<]+?>', '', str(otp_raw)).strip()
                        uid = f"{num}_{clean_c[:10]}"
                        if uid not in done_ids:
                            process_sms_logic(num, clean_c, "x.mnitnetwork")
                            done_ids.add(uid)
            
            if len(done_ids) > 300: done_ids.clear()
            time.sleep(4)
        except: time.sleep(5)

if __name__ == "__main__":
    # Notif bot aktif
    kirim_tele("🚀 <b>BOT DUAL-PANEL AKTIF!</b>\nCallTime & X-MNIT standby 24 Jam.")
    
    threading.Thread(target=run_manager, daemon=True).start()
    threading.Thread(target=run_grabber, daemon=True).start()
    while True: time.sleep(10)
