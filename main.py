import threading, time, os, re, random, requests, json
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_req

# === CONFIG ===
FIREBASE_URL = os.getenv("FIREBASE_URL", "").strip().rstrip('/')
MY_COOKIE = os.getenv("MY_COOKIE", "").strip()      # CallTime
MNIT_COOKIE = os.getenv("MNIT_COOKIE", "").strip()  # X-MNIT
MNIT_TOKEN = os.getenv("MNIT_TOKEN", "").strip()    # mauthtoken
MY_UA = os.getenv("MY_UA", "").strip()              # User Agent
TELE_TOKEN = os.getenv("TELE_TOKEN", "").strip()
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID", "").strip()

sudah_diproses = set()

def send_tele(text):
    if not TELE_TOKEN or not TELE_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        otp_match = re.search(r'\d{4,8}', text)
        if otp_match:
            otp = otp_match.group(0)
            text = text.replace(otp, f"<code>{otp}</code>")
        requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
    except: pass

def cari_pemilik_brutal(clean_num):
    """Mencari pemilik nomor di seluruh folder members jika lookup gagal"""
    try:
        # 1. Cek di lookup cepat dulu
        owner = requests.get(f"{FIREBASE_URL}/active_numbers_lookup/{clean_num}.json").json()
        if owner: return owner
        
        # 2. Jika gagal, ubek-ubek seluruh folder members
        all_members = requests.get(f"{FIREBASE_URL}/members.json").json()
        if all_members:
            for m_id, m_data in all_members.items():
                active = m_data.get('active_numbers', {})
                if isinstance(active, dict):
                    if clean_num in active:
                        return active[clean_num]
        return None
    except: return None

# ==========================================
# 1. MANAGER: PROSES AMBIL NOMOR
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
                tipe_stok = str(item.get('type', '')).upper()
                situs = "CallTime" if "PREFIX" not in tipe_stok else "x.mnitnetwork"
                
                if situs == "CallTime":
                    nums = item.get('stock') or item.get('stok') or []
                    if nums and len(nums) > 0:
                        nomor_hasil = nums.pop(0)
                        requests.put(f"{FIREBASE_URL}/inventory/{inv_id}/stock.json", json=nums)
                else:
                    target_range = item.get('prefixes') or item.get('prefix')
                    h = {'content-type':'application/json','cookie':MNIT_COOKIE,'mauthtoken':MNIT_TOKEN,'user-agent':MY_UA}
                    res_x = curl_req.post("https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number", headers=h, json={"range":target_range}, impersonate="chrome", timeout=20)
                    if res_x.status_code == 200: nomor_hasil = res_x.json().get('data', {}).get('copy')

                if nomor_hasil:
                    clean_n = re.sub(r'\D', '', str(nomor_hasil))
                    data_final = {
                        "number": str(nomor_hasil), "name": m_name, "country": item.get('serviceName') or item.get('name'),
                        "situs": situs, "timestamp": int(time.time() * 1000)
                    }
                    requests.patch(f"{FIREBASE_URL}/members/{m_id}/active_numbers/{clean_n}.json", json=data_final)
                    requests.patch(f"{FIREBASE_URL}/active_numbers_lookup/{clean_n}.json", json=data_final)
                    print(f"✅ Nomor {nomor_hasil} dialokasikan ke {m_name}")
            
            if len(sudah_diproses) > 100: sudah_diproses.clear()
            time.sleep(1)
        except: time.sleep(5)

# ==========================================
# 2. GRABBER: SMS (HISTORY & REALTIME)
# ==========================================
def process_incoming_sms(num, msg, situs_asal):
    try:
        clean_num = re.sub(r'\D', '', str(num))
        # Pencarian pemilik yang lebih brutal/teliti
        owner = cari_pemilik_brutal(clean_num)
        
        if owner:
            # Bersihkan pesan
            clean_msg = msg.replace('u003c#u003e', '').replace('u003e', '').strip()
            
            text_tele = (f"📩 <b>SMS BARU!</b>\n\n"
                        f"👤 Nama : {owner['name']}\n"
                        f"📱 Nomor : <code>{owner['number']}</code>\n"
                        f"🌍 Negara : {owner['country']}\n"
                        f"📌 Situs : {owner['situs']}\n"
                        f"💬 Pesan : {clean_msg}")
            send_tele(text_tele)
            
            # Post ke Firebase Global Messages
            requests.post(f"{FIREBASE_URL}/messages.json", json={"liveSms": owner['number'], "messageContent": clean_msg, "timestamp": int(time.time() * 1000)})
            print(f"✅ Berhasil Grab SMS {clean_num} dari {situs_asal}")
    except: pass

def run_grabber():
    print("📡 GRABBER: Scanning SMS...")
    done_ids = set()
    h_mnit = {'cookie': MNIT_COOKIE,'mauthtoken': MNIT_TOKEN,'user-agent': MY_UA,'accept': 'application/json','x-requested-with': 'XMLHttpRequest'}
    
    while True:
        try:
            # --- 🛰️ SCAN CALLTIME (HISTORY MODE) ---
            res_ct = requests.get(f"https://www.calltimepanel.com/yeni/SMS/?_={int(time.time()*1000)}", headers={'Cookie': MY_COOKIE}, timeout=15)
            if res_ct.status_code == 200:
                soup = BeautifulSoup(res_ct.text, 'html.parser')
                for r in soup.select('table tr'):
                    tds = r.find_all('td')
                    if len(tds) < 4: continue
                    # Ambil angka nomor HP paling belakang
                    raw_n = tds[1].text.strip()
                    num_match = re.findall(r'\d+', raw_n)
                    if not num_match: continue
                    n = num_match[-1]
                    
                    m = tds[2].text.strip()
                    uid = f"ct_{n}_{m[:15]}"
                    if uid not in done_ids:
                        process_incoming_sms(n, m, "CallTime")
                        done_ids.add(uid)

            # --- 📡 SCAN X-MNIT ---
            tgl = time.strftime("%Y-%m-%d")
            url_mn = f"https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?date={tgl}&page=1&search=&status="
            res_mn = curl_req.get(url_mn, headers=h_mnit, impersonate="chrome", timeout=15)
            if res_mn.status_code == 200:
                data_mnit = res_mn.json().get('data', {}).get('numbers', [])
                for it in data_mnit:
                    num, otp_raw = it.get('number'), it.get('otp')
                    if num and otp_raw and "Waiting" not in otp_raw:
                        clean_c = re.sub('<[^<]+?>', '', str(otp_raw)).strip()
                        uid = f"mn_{num}_{clean_c[:10]}"
                        if uid not in done_ids:
                            process_incoming_sms(num, clean_c, "x.mnitnetwork")
                            done_ids.add(uid)
            
            if len(done_ids) > 500: done_ids.clear()
            time.sleep(4)
        except: time.sleep(5)

if __name__ == "__main__":
    send_tele("🚀 <b>BOT TESTER HISTORY AKTIF!</b>\nMencoba menarik semua SMS lama...")
    threading.Thread(target=run_manager, daemon=True).start()
    threading.Thread(target=run_grabber, daemon=True).start()
    while True: time.sleep(10)
