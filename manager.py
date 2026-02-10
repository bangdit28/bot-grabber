import random, time, os, requests
from curl_cffi import requests as curl_req

FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MNIT_COOKIE = os.getenv("MNIT_COOKIE")
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
MY_UA = os.getenv("MY_UA")

def tembak_mnit(prefixes):
    if not prefixes: return None
    target = random.choice(prefixes)
    url = "https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number"
    headers = {'content-type': 'application/json','cookie': MNIT_COOKIE,'mauthtoken': MNIT_TOKEN,'user-agent': MY_UA}
    try:
        res = curl_req.post(url, headers=headers, json={"range": target}, impersonate="chrome", timeout=30)
        return res.json().get('data', {}).get('copy')
    except: return None

def bot_manager_run():
    print("🚀 Manager Running: Mengelola Antrian...")
    while True:
        try:
            # Cek Antrian
            cmds = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if not cmds:
                time.sleep(2); continue
            
            # Cek Inventory
            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()

            for cmd_id, val in cmds.items():
                m_id = val.get('memberId')
                inv_id = val.get('inventoryId')
                
                stok_item = inv.get(inv_id)
                if not stok_item: continue

                nomor_hasil = None
                # Logika Ambil Sesuai Tipe di Inventory
                if stok_item['type'] == 'manual':
                    numbers = stok_item.get('stock', [])
                    if numbers:
                        # Jika list
                        if isinstance(numbers, list):
                            nomor_hasil = numbers.pop(0)
                            requests.put(f"{FIREBASE_URL}/inventory/{inv_id}/stock.json", json=numbers)
                        else: # Jika dict
                            key = list(numbers.keys())[0]
                            nomor_hasil = numbers[key]
                            requests.delete(f"{FIREBASE_URL}/inventory/{inv_id}/stock/{key}.json")
                
                elif stok_item['type'] == 'xmnit':
                    nomor_hasil = tembak_mnit(stok_item.get('prefixes', []))

                if nomor_hasil:
                    # Simpan ke Path Member
                    flag = f"https://flagcdn.com/w80/{stok_item.get('flag', 'id').lower()}.png"
                    requests.post(f"{FIREBASE_URL}/members/{m_id}/active_numbers.json", json={
                        "number": nomor_hasil,
                        "name": stok_item['name'],
                        "flag": flag,
                        "timestamp": int(time.time() * 1000)
                    })
                
                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
            time.sleep(1)
        except: time.sleep(5)
