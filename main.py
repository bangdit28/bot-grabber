import threading, time, os, re, random, requests
from curl_cffi import requests as curl_req

FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MY_COOKIE = os.getenv("MY_COOKIE")
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
MY_UA = os.getenv("MY_UA")

def run_manager():
    print("🚀 Manager Running...")
    while True:
        try:
            res_fire = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if not res_fire:
                time.sleep(1); continue
            
            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()
            for cmd_id, val in res_fire.items():
                m_id = val.get('memberId', 'ADMIN') # Default ke ADMIN kalo kosong
                inv_id = val.get('inventoryId')
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
                            k = list(nums.keys())[0]; nomor_hasil = nums[k]
                            requests.delete(f"{FIREBASE_URL}/inventory/{inv_id}/stock/{k}.json")
                
                elif stok_item['type'] == 'xmnit':
                    target = random.choice(stok_item.get('prefixes', []))
                    h = {'content-type':'application/json','cookie':MNIT_COOKIE,'mauthtoken':MNIT_TOKEN,'user-agent':MY_UA}
                    res = curl_req.post("https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number", headers=h, json={"range":target}, impersonate="chrome", timeout=20)
                    if res.status_code == 200:
                        nomor_hasil = res.json().get('data', {}).get('copy')

                if nomor_hasil:
                    data_final = {
                        "number": str(nomor_hasil),
                        "name": stok_item.get('name', 'Unknown'),
                        "timestamp": int(time.time() * 1000)
                    }
                    # BOM 1: Masuk ke folder spesifik member (members/ADMIN/active_numbers)
                    requests.post(f"{FIREBASE_URL}/members/{m_id}/active_numbers.json", json=data_final)
                    
                    # BOM 2: Masuk ke folder global (active_numbers) buat jaga-jaga
                    requests.post(f"{FIREBASE_URL}/active_numbers.json", json=data_final)
                    
                    print(f"✅ SUKSES: {nomor_hasil} terkirim ke {m_id}")

                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
            time.sleep(1)
        except: time.sleep(5)

def run_grabber():
    print("📡 Grabber SMS Aktif...")
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
                        if f"{num}_{clean_code}" not in done_ids:
                            # Kirim OTP ke path global /messages
                            requests.post(f"{FIREBASE_URL}/messages.json", json={
                                "liveSms": num,
                                "messageContent": f"Your code is {clean_code}",
                                "timestamp": int(time.time() * 1000)
                            })
                            done_ids.append(f"{num}_{clean_code}")
            time.sleep(3)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_manager, daemon=True).start()
    threading.Thread(target=run_grabber, daemon=True).start()
    while True: time.sleep(10)
