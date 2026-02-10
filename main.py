import threading
import time
import os
import re
import random
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_req

# === CONFIG ===
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MY_COOKIE = os.getenv("MY_COOKIE")      # CallTime
MNIT_COOKIE = os.getenv("MNIT_COOKIE")  # X-MNIT
MNIT_TOKEN = os.getenv("MNIT_TOKEN")    # Mauthtoken
MY_UA = os.getenv("MY_UA")              # User Agent
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

def send_or_edit_tele(text, msg_id=None):
    """Fungsi kirim notif baru atau edit notif lama"""
    try:
        if msg_id: # Edit pesan
            url = f"https://api.telegram.org/bot{TELE_TOKEN}/editMessageText"
            data = {'chat_id': TELE_CHAT_ID, 'message_id': msg_id, 'text': text, 'parse_mode': 'HTML'}
        else: # Kirim pesan baru
            url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
            data = {'chat_id': TELE_CHAT_ID, 'text': text, 'parse_mode': 'HTML'}
        
        res = requests.post(url, data=data, timeout=10).json()
        return res.get('result', {}).get('message_id')
    except: return None

# ==========================================
# 1. MANAGER (PENGATUR AMBIL NOMOR)
# ==========================================
def run_manager():
    print("🚀 Manager Running: Multi-Team System Active...")
    while True:
        try:
            cmds = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if not cmds:
                time.sleep(1); continue
            
            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()
            for cmd_id, val in cmds.items():
                m_id = val.get('memberId')
                m_name = val.get('memberName', 'Admin') # Nama asli anggota
                inv_id = val.get('inventoryId')
                
                stok_item = inv.get(inv_id) if inv else None
                if not stok_item: 
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
                    continue

                nomor_hasil = None
                situs = "CallTime" if stok_item['type'] == 'manual' else "x.mnitnetwork"
                
                # --- PROSES AMBIL NOMOR ---
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
                    headers = {'content-type': 'application/json','cookie': MNIT_COOKIE,'mauthtoken': MNIT_TOKEN,'user-agent': MY_UA}
                    res = curl_req.post("https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number", headers=headers, json={"range": target}, impersonate="chrome", timeout=20)
                    if res.status_code == 200:
                        nomor_hasil = res.json().get('data', {}).get('copy')

                if nomor_hasil:
                    # Notif Telegram Pertama: Berhasil Ambil Nomor
                    text_start = (
                        f"📞 <b>BERHASIL AMBIL NOMOR!</b>\n\n"
                        f"👤 <b>Nama :</b> {m_name}\n"
                        f"📱 <b>Nomor :</b> <code>{nomor_hasil}</code>\n"
                        f"📌 <b>Situs :</b> {situs}\n"
                        f"🌍 <b>Negara :</b> {stok_item.get('name', 'Unknown')}\n"
                        f"💬 <b>Pesan :</b> Menunggu sms . . ."
                    )
                    tele_id = send_or_edit_tele(text_start)

                    # Simpan ke Firebase Member + Simpan Tele ID buat diedit nanti
                    flag_url = f"https://flagcdn.com/w80/{stok_item.get('flag', 'id').lower()}.png"
                    data_save = {
                        "number": nomor_hasil,
                        "name": m_name,
                        "country": stok_item['name'],
                        "situs": situs,
                        "flag": flag_url,
                        "tele_msg_id": tele_id,
                        "timestamp": int(time.time() * 1000)
                    }
                    # Simpan di list anggota dan list global grabber
                    requests.post(f"{FIREBASE_URL}/members/{m_id}/active_numbers.json", json=data_save)
                    requests.patch(f"{FIREBASE_URL}/active_numbers_lookup/{nomor_hasil.replace('+','')}.json", json=data_save)

                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
            time.sleep(1)
        except Exception as e:
            print(f"Manager Error: {e}")
            time.sleep(5)

# ==========================================
# 2. GRABBER (PENGAMBIL SMS & EDIT NOTIF)
# ==========================================
def process_sms(num, msg):
    try:
        # Cari siapa pemilik nomor ini
        clean_num = str(num).replace('+','')
        owner_data = requests.get(f"{FIREBASE_URL}/active_numbers_lookup/{clean_num}.json").json()
        
        if owner_data:
            # Format OTP Biar Klik Salin
            otp_match = re.search(r'\d{4,8}', msg)
            clean_msg = msg
            if otp_match:
                otp = otp_match.group(0)
                clean_msg = msg.replace(otp, f"<code>{otp}</code>")

            # Update ke Notif Telegram yang sama (EDIT)
            text_sms = (
                f"📩 <b>SMS MASUK!</b>\n\n"
                f"👤 <b>Nama :</b> {owner_data['name']}\n"
                f"📱 <b>Nomor :</b> <code>{num}</code>\n"
                f"📌 <b>Situs :</b> {owner_data['situs']}\n"
                f"🌍 <b>Negara :</b> {owner_data['country']}\n"
                f"💬 <b>Pesan :</b> {clean_msg}"
            )
            send_or_edit_tele(text_sms, owner_data.get('tele_msg_id'))
            
            # Simpan ke folder messages buat Web
            requests.post(f"{FIREBASE_URL}/messages.json", json={"liveSms": num, "messageContent": msg, "timestamp": int(time.time()*1000)})
            # Hapus lookup biar gak double grab
            requests.delete(f"{FIREBASE_URL}/active_numbers_lookup/{clean_num}.json")
    except: pass

def run_grabber():
    print("📡 SMS Grabber Aktif...")
    done_ids = []
    while True:
        try:
            # Grab CallTime
            res_ct = requests.get(f"https://www.calltimepanel.com/yeni/SMS/?_={int(time.time()*1000)}", headers={'Cookie': MY_COOKIE}, timeout=10)
            soup = BeautifulSoup(res_ct.text, 'html.parser')
            for r in soup.select('table tr'):
                c = r.find_all('td')
                if len(c) < 4: continue
                num = c[1].text.strip().split('-')[-1].strip()
                msg = c[2].text.strip()
                if f"{num}_{msg[:5]}" not in done_ids:
                    process_sms(num, msg)
                    done_ids.append(f"{num}_{msg[:5]}")

            # Grab X-MNIT
            tgl = time.strftime("%Y-%m-%d")
            url_mnit = f"https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?date={tgl}&page=1&search=&status="
            res_mn = curl_req.get(url_mnit, headers={'cookie': MNIT_COOKIE,'mauthtoken': MNIT_TOKEN,'user-agent': MY_UA}, impersonate="chrome", timeout=15)
            if res_mn.status_code == 200:
                items = res_mn.json().get('data', {}).get('data', [])
                for item in items:
                    num, code = item.get('copy'), item.get('code')
                    if num and code:
                        clean_code = re.sub('<[^<]+?>', '', str(code)).strip()
                        if f"{num}_{clean_code}" not in done_ids:
                            process_sms(num, f"Your code is {clean_code}")
                            done_ids.append(f"{num}_{clean_code}")
            time.sleep(3)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_manager, daemon=True).start()
    threading.Thread(target=run_grabber, daemon=True).start()
    while True: time.sleep(10)
