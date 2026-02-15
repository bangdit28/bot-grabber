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

# --- CACHE DATA (Supaya tidak spam request ke Firebase) ---
CACHE_DATA = {
    "inventory": {},
    "members": {},
    "team": {},
    "last_update": 0
}

def update_cache():
    """Refresh data dari Firebase setiap 60 detik"""
    if time.time() - CACHE_DATA["last_update"] > 60:
        try:
            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json() or {}
            mem = requests.get(f"{FIREBASE_URL}/members.json").json() or {}
            team = requests.get(f"{FIREBASE_URL}/app_data/team.json").json() or {}
            
            CACHE_DATA["inventory"] = inv
            CACHE_DATA["members"] = mem
            CACHE_DATA["team"] = team
            CACHE_DATA["last_update"] = time.time()
        except Exception as e:
            print(f"Cache Update Error: {e}")

def get_flag_emoji(country_code):
    """Convert kode negara (id, us) jadi emoji bendera"""
    if not country_code: return "🏳️"
    try:
        return "".join([chr(ord(c.upper()) + 127397) for c in country_code])
    except:
        return "🏳️"

def cari_info_lengkap(nomor):
    """
    Mencari detail lengkap: Nama Member, Apps, Negara, Server, Flag
    """
    update_cache()
    clean_num = str(nomor).strip()
    
    info = {
        "nama": "ADMIN",
        "apps": "SERVICE",
        "negara": "UNKNOWN",
        "server": "Server",
        "flag": "🏳️"
    }
    
    # Loop cari pemilik nomor di data members
    for m_id, m_data in CACHE_DATA["members"].items():
        active = m_data.get('active_numbers', {})
        for k, v in active.items():
            db_num = str(v.get('number', '')).strip()
            # Cek kecocokan nomor
            if db_num and (clean_num in db_num or db_num in clean_num):
                # 1. AMBIL NAMA ASLI (Dari app_data/team)
                team_data = CACHE_DATA["team"].get(m_id, {})
                info["nama"] = team_data.get('name', 'User').upper()
                
                # 2. AMBIL INFO SERVER & NEGARA (Dari inventory)
                inv_id = v.get('inventoryId')
                if inv_id and inv_id in CACHE_DATA["inventory"]:
                    item = CACHE_DATA["inventory"][inv_id]
                    info["apps"] = str(item.get('serviceName', 'Service')).upper()
                    info["server"] = str(item.get('serviceName', 'Server'))
                    info["negara"] = str(item.get('countryName', item.get('countryCode', 'Unknown'))).upper()
                    info["flag"] = get_flag_emoji(item.get('countryCode', 'id'))
                else:
                    # Fallback jika inventory dihapus tapi history ada
                    code = v.get('country', 'id')
                    info["flag"] = get_flag_emoji(code)
                    info["negara"] = f"Code {code.upper()}"
                
                return info
    
    return info

def kirim_tele(pesan_html):
    if not TELE_TOKEN or not TELE_CHAT_ID: return
    try:
        url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
        data = {'chat_id': TELE_CHAT_ID, 'text': pesan_html, 'parse_mode': 'HTML'}
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(f"Tele Error: {e}")

# ==========================================
# 1. MANAGER (AMBIL NOMOR)
# ==========================================
def run_manager():
    print("🚀 Manager CallTime Started...")
    while True:
        try:
            res = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if not res or not isinstance(res, dict):
                time.sleep(1.5); continue
            
            update_cache() # Pastikan inventory terbaru
            inv = CACHE_DATA["inventory"]
            
            for cmd_id, val in res.items():
                if not isinstance(val, dict): continue
                
                m_id = val.get('memberId')
                m_name = val.get('memberName', 'User')
                inv_id = val.get('inventoryId')
                
                item = inv.get(inv_id)
                if not item:
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
                    continue

                nomor_hasil = None
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
                    # Simpan
                    data_save = {
                        "number": str(nomor_hasil),
                        "country": item.get('countryCode', 'id'),
                        "inventoryId": inv_id,
                        "timestamp": int(time.time() * 1000)
                    }
                    requests.post(f"{FIREBASE_URL}/members/{m_id}/active_numbers.json", json=data_save)
                    
                    # Notif Tele Manager
                    flag = get_flag_emoji(item.get('countryCode', 'id'))
                    kirim_tele(
                        f"✅ <b>BERHASIL AMBIL NOMOR!</b>\n\n"
                        f"👤 <b>Anggota:</b> {m_name}\n"
                        f"📱 <b>Nomor:</b> <code>{nomor_hasil}</code>\n"
                        f"🌍 <b>Server:</b> {item.get('serviceName')} {flag}"
                    )
                    print(f"✅ Allocated: {nomor_hasil} -> {m_name}")
                else:
                    kirim_tele(f"❌ <b>STOK HABIS!</b>\nServer: {item.get('serviceName')}\nUser: {m_name}")

                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
            time.sleep(1)
        except Exception as e:
            print(f"Manager Error: {e}")
            time.sleep(5)

# ==========================================
# 2. GRABBER (AMBIL SMS)
# ==========================================
def run_grabber():
    print("🛰️ Grabber SMS CallTime Started...")
    done_ids = []
    
    # Load processed IDs supaya gak spam pas restart
    try:
        msgs = requests.get(f"{FIREBASE_URL}/messages.json?orderBy=\"$key\"&limitToLast=50").json()
        if msgs:
            for k, v in msgs.items():
                uid = f"{v.get('liveSms', '')}_{v.get('messageContent', '')[:10]}"
                done_ids.append(uid)
    except: pass

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
                    # 1. Cari Info Lengkap (Nama, Apps, Negara, Flag)
                    info = cari_info_lengkap(num)
                    
                    # 2. Push ke Firebase (Agar Web Dashboard Update)
                    requests.post(f"{FIREBASE_URL}/messages.json", json={
                        "liveSms": num,
                        "messageContent": msg,
                        "ownerName": info['nama'], # Nama Member Asli
                        "sid": info['apps'],       # Nama Apps/Service
                        "timestamp": int(time.time() * 1000)
                    })
                    
                    # 3. Format Pesan Telegram (Sesuai Request)
                    # Highlight OTP
                    otp_match = re.search(r'\b\d{4,8}\b', msg)
                    clean_msg = msg
                    if otp_match:
                        clean_msg = msg.replace(otp_match.group(0), f"<code>{otp_match.group(0)}</code>")

                    text_tele = (
                        f"📩 <b>SMS DITERIMA!</b>\n\n"
                        f"👤 <b>Nama :</b> {info['nama']}\n"
                        f"📱 <b>Nomor :</b> <code>{num}</code>\n"
                        f"📌 <b>Apps :</b> {info['apps']}\n"
                        f"🌍 <b>Negara :</b> {info['negara']} : {info['server']} {info['flag']}\n"
                        f"💬 <b>Pesan :</b> {clean_msg}"
                    )
                    
                    kirim_tele(text_tele)
                    done_ids.append(uid)
                    print(f"📩 SMS: {num} | {info['nama']} | {info['apps']}")
            
            if len(done_ids) > 200: done_ids = done_ids[-100:]
            time.sleep(4)
        except Exception as e:
            print(f"Grabber Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    t1 = threading.Thread(target=run_manager, daemon=True)
    t2 = threading.Thread(target=run_grabber, daemon=True)
    t1.start()
    t2.start()
    
    kirim_tele("🚀 <b>BOT PYTHON RESTARTED!</b>\nFormat notifikasi baru telah aktif.")
    while True:
        time.sleep(10)
