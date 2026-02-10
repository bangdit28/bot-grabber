import threading, time, os, re, random, requests
from curl_cffi import requests as curl_req

# === CONFIG ===
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MY_COOKIE = os.getenv("MY_COOKIE")
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
MY_UA = os.getenv("MY_UA")

def run_manager():
    print("🚀 Manager Running... Memantau antrian.")
    while True:
        try:
            # 1. Ambil Perintah
            res_fire = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if not res_fire:
                time.sleep(1); continue
            
            # 2. Ambil Inventory (Gudang Stok)
            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()
            
            for cmd_id, val in res_fire.items():
                m_id = val.get('memberId') # Ini harusnya '-OjAKII...'
                inv_id = val.get('inventoryId')
                print(f"📥 Ada perintah dari: {m_id} untuk stok: {inv_id}")

                stok_item = inv.get(inv_id) if inv else None
                if not stok_item:
                    print(f"❌ Stok {inv_id} tidak ketemu di inventory.")
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
                    continue

                nomor_hasil = None
                # LOGIKA AMBIL NOMOR
                if stok_item['type'] == 'manual':
                    nums = stok_item.get('stock', [])
                    if nums:
                        if isinstance(nums, list):
                            nomor_hasil = nums.pop(0)
                            requests.put(f"{FIREBASE_URL}/inventory/{inv_id}/stock.json", json=nums)
                        else:
                            k = list(nums.keys())[0]; nomor_hasil = nums[k]
                            requests.delete(f"{FIREBASE_URL}/inventory/{inv_id}/stock/{k}.json")
                
                elif stok_item['type'] == 'xmnit':
                    target = random.choice(stok_item.get('prefixes', []))
                    h = {'content-type':'application/json','cookie':MNIT_COOKIE,'mauthtoken':MNIT_TOKEN,'user-agent':MY_UA}
                    api_x = "https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number"
                    res = curl_req.post(api_x, headers=h, json={"range":target}, impersonate="chrome", timeout=20)
                    if res.status_code == 200:
                        nomor_hasil = res.json().get('data', {}).get('copy')

                if nomor_hasil:
                    # DATA YANG AKAN DIKIRIM
                    data_final = {
                        "number": str(nomor_hasil),
                        "country": stok_item.get('name', 'Unknown'),
                        "timestamp": int(time.time() * 1000)
                    }
                    
                    # --- SYNC KE PATH YANG DICARI WEB LO ---
                    # Path: members/-OjAKII.../active_numbers
                    target_path = f"{FIREBASE_URL}/members/{m_id}/active_numbers.json"
                    print(f"📤 Menulis nomor ke: {target_path}")
                    
                    post_res = requests.post(target_path, json=data_final)
                    
                    if post_res.status_code == 200:
                        print(f"✅ BERHASIL! Nomor {nomor_hasil} masuk ke Firebase.")
                    else:
                        print(f"❌ GAGAL nulis ke Firebase: {post_res.text}")

                # Hapus antrian
                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
            time.sleep(1)
        except Exception as e:
            print(f"Manager Error: {e}")
            time.sleep(5)

# --- GRABBER SMS (Path /messages) ---
def run_grabber():
    print("📡 SMS Grabber Aktif...")
    done_ids = []
    while True:
        try:
            # Grab X-MNIT
            tgl = time.strftime("%Y-%m-%d")
            url_mnit = f"https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/info?date={tgl}&page=1&search=&status="
            res = curl_req.get(url_mnit, headers={'cookie':MNIT_COOKIE,'mauthtoken':MNIT_TOKEN,'user-agent':MY_UA}, impersonate="chrome", timeout=15)
            if res.status_code == 200:
                items = res.json().get('data', {}).get('data', [])
                for it in items:
                    num, code = it.get('copy'), it.get('code')
                    if num and code:
                        clean_code = re.sub('<[^<]+?>', '', str(code)).strip()
                        uid = f"{num}_{clean_code}"
                        if uid not in done_ids:
                            requests.post(f"{FIREBASE_URL}/messages.json", json={
                                "liveSms": num,
                                "messageContent": f"Your code is {clean_code}",
                                "timestamp": int(time.time() * 1000)
                            })
                            done_ids.append(uid)
            time.sleep(3)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_manager, daemon=True).start()
    threading.Thread(target=run_grabber, daemon=True).start()
    while True: time.sleep(10)
