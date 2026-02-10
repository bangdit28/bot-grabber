import threading, time, os, re, random, requests
from curl_cffi import requests as curl_req

FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
MY_UA = os.getenv("MY_UA")

def run_manager():
    print("🚀 BOT MANAGER AKTIF: Menunggu Perintah...")
    while True:
        try:
            # 1. Cek folder perintah_bot
            raw_cmds = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if not raw_cmds:
                time.sleep(1); continue
            
            # 2. Ambil Inventory
            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()
            
            for cmd_id, val in raw_cmds.items():
                m_id = val.get('memberId', 'ADMIN')
                inv_id = val.get('inventoryId')
                print(f"📥 Memproses perintah dari {m_id} untuk stok {inv_id}")

                item = inv.get(inv_id) if inv else None
                if not item:
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
                    continue

                nomor_hasil = None
                # --- LOGIKA AMBIL NOMOR ---
                if item['type'] == 'manual':
                    nums = item.get('stock', [])
                    if nums:
                        if isinstance(nums, list):
                            nomor_hasil = nums.pop(0)
                            requests.put(f"{FIREBASE_URL}/inventory/{inv_id}/stock.json", json=nums)
                        else:
                            k = list(nums.keys())[0]; nomor_hasil = nums[k]
                            requests.delete(f"{FIREBASE_URL}/inventory/{inv_id}/stock/{k}.json")
                
                elif item['type'] == 'xmnit':
                    target = random.choice(item.get('prefixes', ['2367261']))
                    h = {'content-type':'application/json','cookie':MNIT_COOKIE,'mauthtoken':MNIT_TOKEN,'user-agent':MY_UA}
                    res = curl_req.post("https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number", headers=h, json={"range":target}, impersonate="chrome", timeout=20)
                    if res.status_code == 200:
                        nomor_hasil = res.json().get('data', {}).get('copy')

                if nomor_hasil:
                    # SIMPAN KE DATABASE (Akan otomatis bikin folder members)
                    data_save = {
                        "number": str(nomor_hasil),
                        "country": item.get('name', 'Unknown'),
                        "timestamp": int(time.time() * 1000)
                    }
                    path = f"{FIREBASE_URL}/members/{m_id}/active_numbers.json"
                    requests.post(path, json=data_save)
                    print(f"✅ Nomor {nomor_hasil} berhasil dialokasikan!")

                # Hapus perintah setelah diproses
                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
            
            time.sleep(1)
        except Exception as e:
            print(f"Manager Error: {e}")
            time.sleep(5)

def run_grabber():
    # Logika Grabber SMS lo tetap sama (Path /messages)
    pass

if __name__ == "__main__":
    threading.Thread(target=run_manager, daemon=True).start()
    # (Panggil grabber di sini juga)
    while True: time.sleep(10)
