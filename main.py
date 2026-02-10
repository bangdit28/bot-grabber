import threading, time, os, re, random, requests
from curl_cffi import requests as curl_req

# === CONFIG ===
FIREBASE_URL = "https://tasksms-225d1-default-rtdb.asia-southeast1.firebasedatabase.app"
MY_COOKIE = os.getenv("MY_COOKIE") # CallTime
MNIT_COOKIE = os.getenv("MNIT_COOKIE") # X-MNIT
MNIT_TOKEN = os.getenv("MNIT_TOKEN")
MY_UA = os.getenv("MY_UA")

# ==========================================
# 1. LOGIKA AMBIL NOMOR (REQUESTER)
# ==========================================
def run_manager():
    print("🚀 Bot Manager: Menunggu perintah dari Web...")
    while True:
        try:
            # 1. Ambil antrian dari Web
            cmds = requests.get(f"{FIREBASE_URL}/perintah_bot.json").json()
            if not cmds:
                time.sleep(1.5); continue
            
            # 2. Ambil settingan stok/inventory
            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()
            
            for cmd_id, val in cmds.items():
                m_id = val.get('memberId')
                inv_id = val.get('inventoryId')
                stok_item = inv.get(inv_id) if inv else None
                if not stok_item: 
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
                    continue

                nomor_hasil = None
                # PROSES AMBIL NOMOR
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
                    # SIMPAN KE PATH YANG DIBACA WEB: /members/[ID]/active_numbers
                    data_final = {
                        "number": str(nomor_hasil),
                        "country": stok_item.get('name', 'Unknown'),
                        "timestamp": int(time.time() * 1000)
                    }
                    requests.post(f"{FIREBASE_URL}/members/{m_id}/active_numbers.json", json=data_final)
                    # Simpan lookup buat grabber SMS
                    requests.patch(f"{FIREBASE_URL}/active_numbers_lookup/{str(nomor_hasil).replace('+','')}.json", json=data_final)
                    print(f"✅ Nomor {nomor_hasil} sukses dikirim ke {m_id}")

                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
            time.sleep(1)
        except: time.sleep(5)

# ==========================================
# 2. LOGIKA GRABBER SMS
# ==========================================
def run_grabber():
    print("📡 SMS Grabber: Standby narik OTP...")
    done_ids = []
    while True:
        try:
            # --- GRAB X-MNIT ---
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
                            # KIRIM KE /messages (Path yang dibaca Web untuk OTP)
                            requests.post(f"{FIREBASE_URL}/messages.json", json={
                                "liveSms": num,
                                "messageContent": f"Your Facebook code is {clean_code}",
                                "timestamp": int(time.time() * 1000)
                            })
                            done_ids.append(uid)
                            print(f"📩 OTP Grabbed: {num} -> {clean_code}")
            
            # --- GRAB CALLTIME (Optional) ---
            res_ct = requests.get(f"https://www.calltimepanel.com/yeni/SMS/?_={int(time.time()*1000)}", headers={'Cookie': MY_COOKIE}, timeout=10)
            soup = BeautifulSoup(res_ct.text, 'html.parser')
            for r in soup.select('table tr'):
                c = r.find_all('td')
                if len(c) < 4: continue
                n = c[1].text.strip().split('-')[-1].strip()
                m = c[2].text.strip()
                if f"{n}_{m[:5]}" not in done_ids:
                    requests.post(f"{FIREBASE_URL}/messages.json", json={"liveSms": n, "messageContent": m, "timestamp": int(time.time()*1000)})
                    done_ids.append(f"{n}_{m[:5]}")

            time.sleep(3)
        except: time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=run_manager, daemon=True).start()
    threading.Thread(target=run_grabber, daemon=True).start()
    while True: time.sleep(10)
