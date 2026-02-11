import threading, time, os, requests
from bs4 import BeautifulSoup

# --- CONFIG ---
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MY_COOKIE = os.getenv("MY_COOKIE") # Cookie CallTime lo

def run_manager():
    """Tugas: Ambil nomor dari inventory ke member"""
    print("🚀 Manager CallTime Aktif...")
    while True:
        try:
            # 1. Ambil Antrian Perintah
            res = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if not res or not isinstance(res, dict):
                time.sleep(2); continue
            
            # 2. Ambil Data Inventory
            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()
            
            for cmd_id, val in res.items():
                if not isinstance(val, dict): continue
                
                m_id = val.get('memberId')
                inv_id = val.get('inventoryId')
                print(f"📥 Memproses stok untuk {m_id}")

                item = inv.get(inv_id) if inv else None
                if not item or item.get('type') != 'manual':
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
                    continue

                # --- PROSES AMBIL STOK MANUAL ---
                nums = item.get('stock', [])
                nomor_hasil = None
                
                if nums:
                    if isinstance(nums, list):
                        nomor_hasil = nums.pop(0)
                        requests.put(f"{FIREBASE_URL}/inventory/{inv_id}/stock.json", json=nums)
                    else: # Jika format object/dict
                        key = list(nums.keys())[0]
                        nomor_hasil = nums[key]
                        requests.delete(f"{FIREBASE_URL}/inventory/{inv_id}/stock/{key}.json")

                if nomor_hasil:
                    # 3. KIRIM KE LIST 'MY ACTIVE NUMBERS' ANGGOTA
                    data_save = {
                        "number": str(nomor_hasil),
                        "name": item.get('name', 'CallTime'),
                        "timestamp": int(time.time() * 1000)
                    }
                    # Kirim ke folder members/[ID]/active_numbers
                    requests.post(f"{FIREBASE_URL}/members/{m_id}/active_numbers.json", json=data_save)
                    print(f"✅ Nomor {nomor_hasil} masuk ke Dashboard {m_id}")
                
                # Hapus perintah
                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
            
            time.sleep(1)
        except Exception as e:
            print(f"Error Manager: {e}")
            time.sleep(5)

def run_grabber():
    """Tugas: Grab SMS CallTime Masuk"""
    print("🛰️ Grabber SMS CallTime Aktif...")
    done_ids = []
    while True:
        try:
            res = requests.get(f"https://www.calltimepanel.com/yeni/SMS/?_={int(time.time()*1000)}", 
                               headers={'Cookie': MY_COOKIE}, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            for r in soup.select('table tr'):
                c = r.find_all('td')
                if len(c) < 4: continue
                num = c[1].text.strip().split('-')[-1].strip()
                msg = c[2].text.strip()
                uid = f"{num}_{msg[:5]}"
                if uid not in done_ids:
                    # Simpan SMS ke folder global /messages (biar web bisa narik)
                    requests.post(f"{FIREBASE_URL}/messages.json", json={
                        "liveSms": num,
                        "messageContent": msg,
                        "timestamp": int(time.time() * 1000)
                    })
                    done_ids.append(uid)
            time.sleep(4)
        except: time.sleep(5)

if __name__ == "__main__":
    t1 = threading.Thread(target=run_manager)
    t2 = threading.Thread(target=run_grabber)
    t1.start()
    t2.start()
    print("🔥 SISTEM CALLTIME RUNNING 24 JAM!")
