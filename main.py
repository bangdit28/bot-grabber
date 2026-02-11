import threading
import time
import os
import requests
import re
from bs4 import BeautifulSoup

# --- CONFIG DARI KOYEB ---
FIREBASE_URL = os.getenv("FIREBASE_URL", "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app")
MY_COOKIE = os.getenv("MY_COOKIE")
TELE_TOKEN = os.getenv("TELE_TOKEN")
TELE_CHAT_ID = os.getenv("TELE_CHAT_ID")

def kirim_tele(pesan):
    """Fungsi kirim notif ke Telegram dengan format HTML (Klik untuk Salin)"""
    if not TELE_TOKEN or not TELE_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        # Cari angka 4-8 digit (OTP) buat dijadiin monospaced biar gampang disalin
        otp_match = re.search(r'\d{4,8}', pesan)
        clean_msg = pesan
        if otp_match:
            otp = otp_match.group(0)
            clean_msg = pesan.replace(otp, f"<code>{otp}</code>")
            
        data = {'chat_id': TELE_CHAT_ID, 'text': clean_msg, 'parse_mode': 'HTML'}
        requests.post(url, data=data, timeout=10)
    except:
        pass

def cari_pemilik_nomor(nomor):
    """Cari di Firebase siapa anggota yang pegang nomor ini"""
    try:
        res = requests.get(f"{FIREBASE_URL}/members.json").json()
        if res:
            for m_id, data in res.items():
                active = data.get('active_numbers', {})
                for k, v in active.items():
                    # Cocokkan nomor (hapus spasi/karakter aneh)
                    if str(nomor).strip() in str(v.get('number')).strip():
                        return v.get('name', m_id)
        return "Admin"
    except:
        return "Admin"

# ==========================================
# 1. MANAGER (AMBIL NOMOR DARI STOK)
# ==========================================
def run_manager():
    print("🚀 Manager CallTime Started...")
    while True:
        try:
            # Cek perintah dari web
            res = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if not res or not isinstance(res, dict):
                time.sleep(1.5); continue
            
            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()
            
            for cmd_id, val in res.items():
                if not isinstance(val, dict): continue
                
                m_id = val.get('memberId')
                m_name = val.get('memberName', 'User')
                inv_id = val.get('inventoryId')
                
                item = inv.get(inv_id) if inv else None
                if not item:
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
                    continue

                nomor_hasil = None
                # Ambil dari stok manual (CallTime Upload)
                if item.get('type') == 'manual':
                    nums = item.get('stock', [])
                    if nums:
                        if isinstance(nums, list):
                            nomor_hasil = nums.pop(0)
                            requests.put(f"{FIREBASE_URL}/inventory/{inv_id}/stock.json", json=nums)
                        else:
                            key = list(nums.keys())[0]
                            nomor_hasil = nums[key]
                            requests.delete(f"{FIREBASE_URL}/inventory/{inv_id}/stock/{key}.json")

                if nomor_hasil:
                    # Simpan ke dashboard anggota
                    data_save = {
                        "number": str(nomor_hasil),
                        "name": item.get('name', 'CallTime'),
                        "timestamp": int(time.time() * 1000)
                    }
                    requests.post(f"{FIREBASE_URL}/members/{m_id}/active_numbers.json", json=data_save)
                    
                    # Notif Telegram Sukses Ambil Nomor
                    text_tele = (
                        f"✅ <b>BERHASIL AMBIL NOMOR!</b>\n\n"
                        f"👤 <b>Anggota:</b> {m_name}\n"
                        f"📱 <b>Nomor:</b> <code>{nomor_hasil}</code>\n"
                        f"🌍 <b>Layanan:</b> {item.get('name')}\n"
                        f"💬 <b>Status:</b> Menunggu SMS masuk..."
                    )
                    kirim_tele(text_tele)
                    print(f"✅ Nomor {nomor_hasil} dialokasikan ke {m_name}")
                else:
                    kirim_tele(f"❌ <b>STOK HABIS!</b>\nLayanan: {item.get('name')}\nAnggota: {m_name}")

                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
            time.sleep(1)
        except Exception as e:
            print(f"Manager Error: {e}")
            time.sleep(5)

# ==========================================
# 2. GRABBER (AMBIL SMS MASUK)
# ==========================================
def run_grabber():
    print("🛰️ Grabber SMS CallTime Started...")
    done_ids = []
    while True:
        try:
            res = requests.get(f"https://www.calltimepanel.com/yeni/SMS/?_={int(time.time()*1000)}", 
                               headers={'Cookie': MY_COOKIE}, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            rows = soup.select('table tr')
            for r in rows:
                c = r.find_all('td')
                if len(c) < 4: continue
                num = c[1].text.strip().split('-')[-1].strip()
                msg = c[2].text.strip()
                
                uid = f"{num}_{msg[:10]}"
                if uid not in done_ids:
                    # Cari siapa yang punya nomor ini
                    owner = cari_pemilik_nomor(num)
                    
                    # Simpan ke Firebase /messages biar muncul di web
                    requests.post(f"{FIREBASE_URL}/messages.json", json={
                        "liveSms": num,
                        "messageContent": msg,
                        "timestamp": int(time.time() * 1000)
                    })
                    
                    # Notif Telegram SMS Masuk
                    text_sms = (
                        f"📩 <b>SMS BARU!</b>\n\n"
                        f"👤 <b>Anggota:</b> {owner}\n"
                        f"📱 <b>Nomor:</b> <code>{num}</code>\n"
                        f"💬 <b>Pesan:</b> {msg}"
                    )
                    kirim_tele(text_sms)
                    done_ids.append(uid)
                    print(f"📩 SMS Masuk: {num}")
            
            if len(done_ids) > 200: done_ids = done_ids[-100:]
            time.sleep(4)
        except:
            time.sleep(5)

if __name__ == "__main__":
    t1 = threading.Thread(target=run_manager, daemon=True)
    t2 = threading.Thread(target=run_grabber, daemon=True)
    t1.start()
    t2.start()
    
    kirim_tele("🚀 <b>BOT CALLTIME AKTIF!</b>\nSistem standby 24 jam. PC boleh dimatikan.")
    while True:
        time.sleep(10)
