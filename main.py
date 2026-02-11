def run_manager():
    print("🚀 Manager Running (Safety Mode Active)...")
    while True:
        try:
            # 1. Ambil Perintah
            r = requests.get(f"{FIREBASE_URL}/perintah_bot.json")
            res_fire = r.json()

            # Jika folder kosong
            if not res_fire:
                time.sleep(1.5); continue
            
            # PENGAMAN: Jika folder perintah_bot isinya cuma tulisan (string) bukan kotak data
            if not isinstance(res_fire, dict):
                print("⚠️ Folder perintah_bot rusak (isinya string). Menghapus folder...")
                requests.delete(f"{FIREBASE_URL}/perintah_bot.json")
                continue

            inv = requests.get(f"{FIREBASE_URL}/inventory.json").json()
            
            for cmd_id, val in res_fire.items():
                # PENGAMAN: Jika isi tiap perintah bukan kotak data (isinya string)
                if not isinstance(val, dict):
                    print(f"🗑️ Menghapus data rusak: {cmd_id}")
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
                    continue

                m_id = val.get('memberId', 'ADMIN')
                inv_id = val.get('inventoryId')
                
                print(f"📥 Memproses perintah dari {m_id}...")

                stok_item = inv.get(inv_id) if inv else None
                if not stok_item:
                    print(f"❌ Stok {inv_id} tidak ketemu.")
                    requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
                    continue

                nomor_hasil = None
                # --- LOGIKA AMBIL NOMOR ---
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
                    target = random.choice(stok_item.get('prefixes', ['2367261']))
                    h = {'content-type':'application/json','cookie':MNIT_COOKIE,'mauthtoken':MNIT_TOKEN,'user-agent':MY_UA}
                    res = curl_req.post("https://x.mnitnetwork.com/mapi/v1/mdashboard/getnum/number", headers=h, json={"range":target}, impersonate="chrome", timeout=20)
                    if res.status_code == 200:
                        nomor_hasil = res.json().get('data', {}).get('copy')

                if nomor_hasil:
                    data_save = {
                        "number": str(nomor_hasil),
                        "country": stok_item.get('name', 'Unknown'),
                        "timestamp": int(time.time() * 1000)
                    }
                    # Simpan ke folder members
                    requests.post(f"{FIREBASE_URL}/members/{m_id}/active_numbers.json", json=data_save)
                    print(f"✅ SUKSES! Nomor {nomor_hasil} terkirim.")

                # Hapus perintah setelah diproses
                requests.delete(f"{FIREBASE_URL}/perintah_bot/{cmd_id}.json")
            
            time.sleep(1)
        except Exception as e:
            print(f"Manager Error: {e}")
            time.sleep(5)
