import threading
import time
import os
import re
import random
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_req

# === CONFIGURATION (AMBIL DARI KOYEB) ===
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MY_COOKIE = os.getenv("MY_COOKIE")      # Cookie CallTime
MNIT_COOKIE = os.getenv("MNIT_COOKIE")  # Cookie X-MNIT
MNIT_TOKEN = os.getenv("MNIT_TOKEN")    # Mauthtoken X-MNIT
MY_UA = os.getenv("MY_UA")              # User Agent Asli
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

# Global Session
session_ct = requests.Session()
session_ct.headers.update({'Cookie': MY_COOKIE})

def kirim_notif_tele(member_name, num, country, msg):
    """Format Notif: Nomor & Kode Klik Auto Salin (Monospaced)"""
    # Cari OTP (angka 4-8 digit) agar tidak disensor dan bisa diklik
    otp_match = re.search(r'\d{4,8}', msg)
    clean_msg = msg
    if otp_match:
        otp = otp_match.group(0)
        clean_msg = msg.replace(otp, f"<code>{otp}</code>")

    text = (
        f"📩 <b>SMS BARU!</b>\n\n"
        f"👤 <b>Nama :</b> {member_name}\n"
        f"📱 <b>Nomor :</b> <code>{num}</code>\n"
        f"🌍 <b>Negara :</b> {country}\n"
        f"💬 <b>Pesan :</b> {clean_msg}"
    )
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': text, 'parse_mode': 'HTML'})

def cari_pemilik_nomor(nomor):
    """Mencari siapa anggota yang memegang nomor ini di Firebase"""
    try:
        members = requests.get(f"{FIREBASE_URL}/members.json").json()
        if members:
            for m_id, data in members.items():
                active = data.get('active_numbers', {})
                for k, v in active.items():
                    # Cek jika nomor cocok (menghilangkan tanda +)
                    if str(nomor).replace('+','') in str(v.get('number')).replace('+',''):
                        return m_id, v.get('name', 'Unknown')
        return "Admin", "Unknown"
    except:
        return "Admin", "Unknown"

# ==========================================
# 1. LOGIKA MANAGER (PENGATUR STOK)
# ==========================================
def run_manager():
    print("🚀 Manager Aktif: Mengelola Antrian...")
    while True:
        try:
            cmds = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if not cmds:
                time.sleep(2); continue
            
            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()
            for cmd_id, val in cmds.items():
                m_id, inv_id = val.get('memberId'), val.get('inventoryId')
                stok_item = inv.get(inv_id)
                if not stok_item: continue

                nomor_hasil = None
                if stok_item['type'] == 'manual':
                    nums = stok_item.get('stock', [])
                    if nums:
                        if isinstance(nums, list):
                            nomor_hasil = nums.pop(0)
                            requests.put(f"{FIREBASE_URL}/inventory/{inv_id}/stock.json", json=nums)
                        else:
                            key = list(nums.keys())[0]
                            nomor_hasil = nums[key]
                            requests.delete(f"{FIREBASE_URL}/inventory/{inv_id}/stock/{key}.json")
                
                elif stok_item['type'] == 'xmnit':
                    target = random.choice(stok_item.get('prefixes', []))
                    url = "https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number"
                    headers = {'content-type': 'application/json','cookie': MNIT_COOKIE,'mauthtoken': MNIT_TOKEN,'user-agent': MY_UA}
                    res = curl_req.post(url, headers=headers, json={"range": target}, impersonate="chrome", timeout=30)
                    if res.status_code == 200:
                        nomor_hasil = res.json().get('data', {}).get('copy')

                if nomor_hasil:
                    flag = f"https://flagcdn.com/w80/{stok_item.get('flag', 'id').lower()}.png"
                    requests.post(f"{FIREBASE_URL}/members/{m_id}/active_numbers.json", json={
                        "number": nomor_hasil, "name": stok_item['name'], "flag": flag, "timestamp": int(time.time() * 1000)
                    })
                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
            time.sleep(1)
        except: time.sleep(5)

# ==========================================
# 2. LOGIKA GRABBER CALLTIME
# ==========================================
def run_calltime():
    print("🛰️ CallTime Grabber Aktif...")
    done_ids = []
    while True:
        try:
            res = session_ct.get(f"https://www.calltimepanel.com/yeni/SMS/?_={int(time.time()*1000)}", timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select('table tbody tr') or soup.select('table tr')
            for r in rows:
                c = r.find_all('td')
                if len(c) < 4: continue
                num = c[1].text.strip().split('-')[-1].strip()
                msg = c[2].text.strip()
                uid = f"{num}_{msg[:10]}"
                if uid not in done_ids:
                    m_name, country = cari_pemilik_nomor(num)
                    requests.post(f"{FIREBASE_URL}/messages.json", json={"liveSms": num, "messageContent": msg, "timestamp": int(time.time()*1000)})
                    kirim_notif_tele(m_name, num, country, msg)
                    done_ids.append(uid)
            time.sleep(4)
        except: time.sleep(5)

# ==========================================
# 3. LOGIKA GRABBER X-MNIT
# ==========================================
def run_xmnit_grabber():
    print("📡 X-MNIT SMS Grabber Aktif...")
    done_ids = []
    headers = {'cookie': MNIT_COOKIE,'mauthtoken': MNIT_TOKEN,'user-agent': MY_UA}
    while True:
        for tgl in [time.strftime("%Y-%m-%d"), time.strftime("%Y-%m-%d", time.localtime(time.time()-86400))]:
            url = f"https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?date={tgl}&page=1&search=&status="
            try:
                res = curl_req.get(url, headers=headers, impersonate="chrome", timeout=30)
                items = res.json().get('data', {}).get('data', [])
                for item in items:
                    num, code = item.get('copy'), item.get('code')
                    if num and code:
                        clean_code = re.sub('<[^<]+?>', '', str(code)).strip()
                        uid = f"{num}_{clean_code}"
                        if uid not in done_ids:
                            m_name, c_name = cari_pemilik_nomor(num)
                            full_msg = f"Your code is {clean_code}"
                            requests.post(f"{FIREBASE_URL}/messages.json", json={"liveSms": num, "messageContent": full_msg, "timestamp": int(time.time()*1000)})
                            kirim_notif_tele(m_name, num, c_name, full_msg)
                            done_ids.append(uid)
            except: pass
        time.sleep(5)

if __name__ == "__main__":
    # Jalankan 3 Mesin Sekaligus
    threading.Thread(target=run_manager, daemon=True).start()
    threading.Thread(target=run_calltime, daemon=True).start()
    threading.Thread(target=run_xmnit_grabber, daemon=True).start()
    
    print("🔥 SEMUA MESIN JALAN! SILAKAN TIDUR NYENYAK.")
    while True:
        time.sleep(10)
