import threading
import time
import os
import re
import random
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_req

# === CONFIGURATION ===
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MY_COOKIE = os.getenv("MY_COOKIE")
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
MY_UA = os.getenv("MY_UA")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

def kirim_notif_tele(member_name, num, country, msg):
    try:
        otp_match = re.search(r'\d{4,8}', msg)
        clean_msg = msg
        if otp_match:
            otp = otp_match.group(0)
            clean_msg = msg.replace(otp, f"<code>{otp}</code>")
        text = (f"📩 <b>SMS BARU!</b>\n\n👤 <b>Nama :</b> {member_name}\n"
                f"📱 <b>Nomor :</b> <code>{num}</code>\n🌍 <b>Negara :</b> {country}\n💬 <b>Pesan :</b> {clean_msg}")
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        requests.post(url, data={'chat_id': TELE_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=5)
    except: pass

def cari_pemilik_nomor(nomor):
    try:
        res = requests.get(f"{FIREBASE_URL}/members.json").json()
        if res:
            for m_id, data in res.items():
                active = data.get('active_numbers', {})
                for k, v in active.items():
                    if str(nomor).strip() in str(v.get('number')).strip():
                        return m_id, v.get('name', m_id)
        return "Admin", "Unknown"
    except: return "Admin", "Unknown"

# ==========================================
# 1. MANAGER (PENGATUR ANTRIAN) - OPTIMIZED
# ==========================================
def run_manager():
    print("🚀 Manager Running (Fast Mode)...")
    while True:
        try:
            # Ambil antrian
            cmds = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if not cmds:
                time.sleep(0.5); continue # Cek lebih cepet (0.5 detik)
            
            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()
            
            for cmd_id, val in cmds.items():
                m_id = val.get('memberId')
                inv_id = val.get('inventoryId')
                print(f"📥 Memproses {m_id} untuk inventory {inv_id}")

                stok_item = inv.get(inv_id) if inv else None
                if not stok_item:
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
                    continue

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
                    res = curl_req.post(url, headers=headers, json={"range": target}, impersonate="chrome", timeout=15)
                    if res.status_code == 200:
                        nomor_hasil = res.json().get('data', {}).get('copy')

                if nomor_hasil:
                    flag = f"https://flagcdn.com/w80/{stok_item.get('flag', 'id').lower()}.png"
                    # SIMPAN KE PATH YANG BENER
                    requests.post(f"{FIREBASE_URL}/members/{m_id}/active_numbers.json", json={
                        "number": nomor_hasil,
                        "name": stok_item['name'],
                        "flag": flag,
                        "timestamp": int(time.time() * 1000)
                    })
                    print(f"✅ Nomor {nomor_hasil} masuk ke {m_id}")
                
                # Hapus perintah SEGERA setelah diproses
                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
        except Exception as e:
            print(f"Error Manager: {e}")
            time.sleep(2)

# ==========================================
# 2. GRABBER CALLTIME & X-MNIT
# ==========================================
def run_grabber():
    print("📡 Grabber SMS Aktif (CallTime + X-MNIT)...")
    done_ids = []
    headers_mnit = {'cookie': MNIT_COOKIE,'mauthtoken': MNIT_TOKEN,'user-agent': MY_UA}
    
    while True:
        try:
            # --- GRAB CALLTIME ---
            res_ct = requests.get(f"https://www.calltimepanel.com/yeni/SMS/?_={int(time.time()*1000)}", timeout=10, headers={'Cookie': MY_COOKIE})
            soup = BeautifulSoup(res_ct.text, 'html.parser')
            for r in (soup.select('table tbody tr') or soup.select('table tr')):
                c = r.find_all('td')
                if len(c) < 4: continue
                num = c[1].text.strip().split('-')[-1].strip()
                msg = c[2].text.strip()
                uid = f"{num}_{msg[:10]}"
                if uid not in done_ids:
                    m_id, m_name = cari_pemilik_nomor(num)
                    requests.post(f"{FIREBASE_URL}/messages.json", json={"liveSms": num, "messageContent": msg, "timestamp": int(time.time()*1000)})
                    kirim_notif_tele(m_name, num, "CallTime", msg)
                    done_ids.append(uid)

            # --- GRAB X-MNIT ---
            tgl = time.strftime("%Y-%m-%d")
            url_mnit = f"https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?date={tgl}&page=1&search=&status="
            res_mn = curl_req.get(url_mnit, headers=headers_mnit, impersonate="chrome", timeout=15)
            if res_mn.status_code == 200:
                items = res_mn.json().get('data', {}).get('data', [])
                for item in items:
                    num, code = item.get('copy'), item.get('code')
                    if num and code:
                        clean_code = re.sub('<[^<]+?>', '', str(code)).strip()
                        uid = f"{num}_{clean_code}"
                        if uid not in done_ids:
                            m_id, m_name = cari_pemilik_nomor(num)
                            full_msg = f"Your code is {clean_code}"
                            requests.post(f"{FIREBASE_URL}/messages.json", json={"liveSms": num, "messageContent": full_msg, "timestamp": int(time.time()*1000)})
                            kirim_notif_tele(m_name, num, "X-MNIT", full_msg)
                            done_ids.append(uid)
            time.sleep(3)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_manager, daemon=True).start()
    threading.Thread(target=run_grabber, daemon=True).start()
    while True: time.sleep(10)
